# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""The three AI check stages. Each builds one StageCall from the run and stores what comes back."""

import os

import fitz
from flask import current_app

from app import db
from app.models import AICheckEvidence, AICheckSource, Company, CompanyResource
from app.services.ai.prompt_service import prompt_service
from app.services.ai_check import AICheckError
from app.services.ai_check.fetch import fetch_source_file
from app.services.ai_check.llm import Document, UsageTally, call_for_tool, record_usage, stage_call
from app.services.ai_check.setup import stage_model
from app.services.ai_check.tools import (
    RECORD_EVIDENCE_TOOL, RECORD_SOURCES_TOOL, REQUEST_MORE_EVIDENCE_TOOL, SUBMIT_AI_CHECK_TOOL,
)
from app.services.ai_check.verify import quote_in_texts, read_page_texts

MAX_SOURCES = 6
MAX_WEB_SOURCES = 4
SEARCH_BUDGET = 5
# Claude's request cap is 32 MB and base64 inflates a PDF by 4/3, so 22 MiB (~29.3 MB encoded) is
# the largest file that still fits with room for the prompt. The same cap applies on every provider.
MAX_DOC_BYTES = 22 * 1024 * 1024
MAX_DOC_PAGES = 600
# Quick sends every ticked document in one request, so the per-document caps apply to the total.
MAX_QUICK_BYTES = MAX_DOC_BYTES
MAX_QUICK_PAGES = MAX_DOC_PAGES


def prompt_data(name):
    """The stage's raw YAML dict. Each stage loads it once and reads its fallback texts from it."""
    return prompt_service.get_prompt_data('research', name)


def render_prompt(data, **variables):
    """The rendered template only; system_context travels separately in the StageCall."""
    return data['template'].format(**variables)


def usage_tally(run):
    """The run's in-flight usage tally (a plain attribute, never a DB column)."""
    tally = getattr(run, '_ai_usage_tally', None)
    if tally is None:
        tally = UsageTally()
        run._ai_usage_tally = tally
    return tally


def _usage_recorder(run):
    return lambda usage: record_usage(usage_tally(run), usage)


def _company_vars(run, data):
    company = db.session.get(Company, run.company_id)
    ctx = run.context_snapshot or {}
    return {
        'company_name': company.name,
        'ticker_symbol': company.ticker_symbol or 'n/a',
        'question': ctx.get('question', ''),
        'method': ctx.get('method', ''),
        'where_to_look': ctx.get('where_to_look') or data['missing_value'],
    }


def _bullets(lines, empty_text):
    return '\n'.join(f'- {line}' for line in lines) if lines else empty_text


def create_document_sources(run):
    resources = CompanyResource.query.filter(
        CompanyResource.id.in_(run.document_ids or []),
        CompanyResource.company_id == run.company_id,
        CompanyResource.user_id == run.user_id,
    ).order_by(CompanyResource.id).all()
    sources = [AICheckSource(run=run, kind='document', company_resource_id=r.id,
                             title=(r.title or r.original_filename or 'Document')[:300])
               for r in resources]
    db.session.add_all(sources)
    db.session.flush()
    return sources


def run_gather(run, adapter, gaps=None):
    web_count = sum(1 for s in run.sources if s.kind == 'web')
    room = min(MAX_SOURCES - len(run.sources), MAX_WEB_SOURCES - web_count)
    searches_left = SEARCH_BUDGET - (run.web_searches or 0)
    if room <= 0 or searches_left <= 0:
        return []
    data = prompt_data('ai_check_gather')
    prompt = render_prompt(
        data, **_company_vars(run, data),
        existing_sources=_bullets([s.title for s in run.sources], data['empty_list']),
        gaps=_bullets(gaps or [], data['empty_list']), max_sources=room)
    call = stage_call(data, stage_model(run, 'gather'), prompt, [RECORD_SOURCES_TOOL],
                      search_cap=min(data.get('search_max_uses', SEARCH_BUDGET), searches_left))
    _, args, _ = call_for_tool(adapter, call, {'record_sources'}, _usage_recorder(run))
    created = []
    for item in args.get('sources') or []:
        url = (item.get('url') or '').strip()
        if not url.startswith(('http://', 'https://')):
            continue
        created.append(AICheckSource(
            run=run, kind='web', url=url[:1000], title=(item.get('title') or url)[:300],
            doc_type=(item.get('doc_type') or '')[:100] or None,
            period=(item.get('period') or '')[:50] or None,
            gap_filled=item.get('gap_filled') or None))
        if len(created) >= room:
            break
    db.session.add_all(created)
    db.session.flush()
    return created


def _as_text(title, page_texts, data):
    body = '\n\n'.join(data['page_marker'].format(number=number) + '\n' + text
                       for number, text in enumerate(page_texts, start=1))
    return data['document_wrapper'].format(title=title, text=body)


def load_document(path, title, data, filename=None):
    """A Document for a local PDF or .txt file, with the size and page caps checked.
    The file type comes from `filename` when given (uploads), otherwise from `path`."""
    if os.path.getsize(path) > MAX_DOC_BYTES:
        raise AICheckError(f'{title} is larger than 22 MB.')
    lower = (filename or path).lower()
    if lower.endswith('.pdf'):
        with fitz.open(path) as doc:
            if doc.page_count > MAX_DOC_PAGES:
                raise AICheckError(f'{title} has more than {MAX_DOC_PAGES} pages.')
        kind = 'pdf'
    elif lower.endswith('.txt'):
        kind = 'text'
    else:
        raise AICheckError(f'{title}: only PDF and .txt files can be read.')
    page_texts = read_page_texts(path)
    return Document(title=title, kind=kind, path=path, page_texts=page_texts,
                    as_text=_as_text(title, page_texts, data))


def _upload_document(run, resource_id, title, upload_folder, data):
    """A Document for one of the user's uploaded files, owned by the run's user and company."""
    resource = CompanyResource.query.filter_by(
        id=resource_id, company_id=run.company_id, user_id=run.user_id).first()
    if resource is None or not resource.stored_filename:
        raise AICheckError(f'{title} no longer exists.')
    path = os.path.join(upload_folder, resource.stored_filename)
    if not os.path.exists(path):
        raise AICheckError(f'{title}: file not found on the server.')
    filename = resource.original_filename or resource.stored_filename
    return load_document(path, filename, data, filename=filename)


def run_extract(source, adapter, upload_folder):
    run = source.run
    data = prompt_data('ai_check_extract')
    if source.kind == 'document':
        document = _upload_document(run, source.company_resource_id, source.title, upload_folder, data)
        instruction = data['document_instruction']
    elif adapter.provider == 'claude' and current_app.config.get('AI_CHECK_CLAUDE_WEB_FETCH', True):
        # Claude fetches the page itself (v1 behaviour); quotes are checked against what it fetched.
        document = None
        instruction = data['url_instruction'].format(url=source.url)
    else:
        path, downloaded = fetch_source_file(source, upload_folder,
                                             current_app.config.get('AI_CHECK_FETCH_CONTACT'))
        if downloaded:
            usage_tally(run).web_fetches += 1
        document = load_document(path, source.title, data)
        instruction = data['attached_url_instruction'].format(url=source.url)
    prompt = render_prompt(data, **_company_vars(run, data),
                           source_title=source.title, source_instruction=instruction)
    call = stage_call(data, stage_model(run, 'extract'), prompt, [RECORD_EVIDENCE_TOOL],
                      documents=[document] if document else [],
                      fetch_cap=None if document else data.get('fetch_max_uses', 2))
    _, args, fetched = call_for_tool(adapter, call, {'record_evidence'}, _usage_recorder(run))
    page_texts = document.page_texts if document else fetched
    evidence = []
    for item in args.get('items') or []:
        if not (item.get('metric') and item.get('value')):
            continue
        evidence.append(AICheckEvidence(
            run_id=run.id, source_id=source.id,
            metric=item['metric'][:300], value=str(item['value'])[:100],
            value_numeric=item.get('value_numeric'),
            unit=(item.get('unit') or '')[:50] or None, period=(item.get('period') or '')[:50] or None,
            location=(item.get('location') or '')[:300] or None, quote=item.get('quote') or None,
            verified=quote_in_texts(item.get('quote'), page_texts)))
    db.session.add_all(evidence)
    db.session.flush()
    return evidence


VERDICTS = ('satisfied', 'not_satisfied', 'needs_attention')
CALC_KINDS = ('line', 'total', 'comparison', 'context')


def assign_labels(run):
    for number, evidence in enumerate(sorted(run.evidence, key=lambda e: e.id), start=1):
        evidence.label = f'E{number}'
    db.session.flush()


def _cell(text):
    """One table cell: no newlines or runs of whitespace, and no '|' (the column separator)."""
    return ' '.join((text or '').replace('|', '/').split())


def evidence_table(run):
    rows = []
    for e in sorted(run.evidence, key=lambda e: e.id):
        where = f'{_cell(e.source.title)} · {_cell(e.location)}' if e.location else _cell(e.source.title)
        rows.append(' | '.join([e.label or '?', _cell(e.metric), _cell(e.value), _cell(e.period), where,
                                'verified' if e.verified else 'unverified', _cell(e.quote)]))
    return '\n'.join(rows)


MAX_KEY_FIGURES = 3


def _text(value):
    return value.strip() if isinstance(value, str) else ''


def clean_result(args, labels, rubric):
    calculation = []
    for line in args.get('calculation') or []:
        calculation.append({
            'label': line.get('label') or '',
            'value': line.get('value') or '',
            'evidence': [label for label in line.get('evidence') or [] if label in labels],
            'note': line.get('note') or None,
            'kind': line.get('kind') if line.get('kind') in CALC_KINDS else 'line',
            'group': _text(line.get('group')) or None,
        })
    key_figures = [
        {'label': _text(fig.get('label')), 'value': _text(fig.get('value')),
         'evidence': [label for label in fig.get('evidence') or [] if label in labels]}
        for fig in args.get('key_figures') or [] if _text(fig.get('label')) and _text(fig.get('value'))
    ][:MAX_KEY_FIGURES]
    verdict = args.get('suggested_verdict')
    # A verdict only counts when the user wrote a rubric line for it; otherwise the model invented the rule.
    if verdict not in VERDICTS or not _text((rubric or {}).get(verdict)):
        verdict = None
    return {
        'headline': _text(args.get('headline')),
        'summary': args.get('summary') or '',
        'key_figures': key_figures,
        'calculation': calculation,
        'suggested_verdict': verdict,
        'verdict_reason': (args.get('verdict_reason') or '') if verdict else '',
        'gaps': [gap for gap in args.get('gaps') or [] if gap],
    }


def run_analyze(run, adapter):
    assign_labels(run)
    ctx = run.context_snapshot or {}
    rubric = ctx.get('verdict_rubric') or {}
    allow_more = not run.loop_back_used and run.mode != 'documents'
    failed = [f'{s.title} ({s.error or s.extract_status})' for s in run.sources
              if s.extract_status in ('failed', 'no_figures')]
    data = prompt_data('ai_check_analyze')
    missing = data['missing_value']
    prompt = render_prompt(
        data, **_company_vars(run, data),
        worked_example=ctx.get('worked_example') or data['missing_example'],
        rubric_satisfied=rubric.get('satisfied') or missing,
        rubric_not_satisfied=rubric.get('not_satisfied') or missing,
        rubric_needs_attention=rubric.get('needs_attention') or missing,
        missing_value=missing,
        evidence_table=evidence_table(run), failed_sources=_bullets(failed, data['empty_list']),
        loop_back_note=data['loop_back_allowed' if allow_more else 'loop_back_closed'])
    tools = [SUBMIT_AI_CHECK_TOOL] + ([REQUEST_MORE_EVIDENCE_TOOL] if allow_more else [])
    names = {tool['name'] for tool in tools}
    name, args, _ = call_for_tool(adapter, stage_call(data, stage_model(run, 'analyze'), prompt, tools), names,
                                  _usage_recorder(run))
    if name == 'request_more_evidence':
        gaps = [str(gap).strip() for gap in args.get('gaps') or [] if str(gap).strip()]
        if not gaps:
            # An untargeted gather would just repeat the first pass; fail at analyzing (retryable).
            raise AICheckError('The model asked for more evidence without naming what is missing.')
        return 'more_evidence', gaps[:5]
    return 'submitted', clean_result(args, {e.label for e in run.evidence}, rubric)


def run_quick(run, adapter, upload_folder):
    """The Quick check: one call answering from the ticked documents and/or web search,
    through submit_ai_check. No evidence table, so calculation lines cite no labels."""
    data = prompt_data('ai_check_quick')
    ctx = run.context_snapshot or {}
    rubric = ctx.get('verdict_rubric') or {}
    missing = data['missing_value']
    documents = [] if run.mode == 'web' else [
        _upload_document(run, resource_id, f'Document {resource_id}', upload_folder, data)
        for resource_id in run.document_ids or []]
    if (sum(os.path.getsize(d.path) for d in documents) > MAX_QUICK_BYTES
            or sum(len(d.page_texts) for d in documents) > MAX_QUICK_PAGES):
        raise AICheckError(data['too_many_documents'])
    search = run.mode in ('web', 'both')
    prompt = render_prompt(
        data, **_company_vars(run, data),
        worked_example=ctx.get('worked_example') or data['missing_example'],
        rubric_satisfied=rubric.get('satisfied') or missing,
        rubric_not_satisfied=rubric.get('not_satisfied') or missing,
        rubric_needs_attention=rubric.get('needs_attention') or missing,
        missing_value=missing,
        documents_note=data['documents_attached' if documents else 'no_documents'],
        search_note=data['search_allowed' if search else 'search_closed'])
    call = stage_call(data, stage_model(run, 'quick'), prompt, [SUBMIT_AI_CHECK_TOOL], documents=documents,
                      search_cap=data.get('search_max_uses', SEARCH_BUDGET) if search else None)
    _, args, _ = call_for_tool(adapter, call, {'submit_ai_check'}, _usage_recorder(run))
    return clean_result(args, set(), rubric)
