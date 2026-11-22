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

"""Checking one must-exit rule: model choice, the answer and search steps, verification,
the stored AIInsight, token charging and the usage log row."""

import logging
from dataclasses import dataclass, replace
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded

from app import db
from app.models import AIInsight, JournalEntry
from app.models.user_ai_preferences import UserAIPreference
from app.services.ai.analytics import log_prompt_usage
from app.services.ai.prompt_service import prompt_service
from app.services.ai_check import AICheckError, setup
from app.services.ai_check.llm import UsageTally, call_for_tool, record_usage, stage_call
from app.services.ai_check.pricing import provider_of
from app.services.decision_journals import current_thesis
from app.services.exit_watch import CONTEXT_TYPE, STATUS_LABELS, STATUS_RANK, ExitWatchError, figures, sources, verdict
from app.services.exit_watch.tools import RECORD_EXIT_CHECK_TOOL, REQUEST_SEARCH_TOOL
from app.services.findings import DEFAULT_SIGNAL, FINDING_TYPES, finding_text_from_editor
from app.utils.time_utils import ensure_timezone_aware, now_utc

LOG = logging.getLogger(__name__)
SEARCH_CAPABLE = setup.STAGE_MODELS['gather']
PROMPT_CATEGORY = 'exit_criteria'
PROMPT_NAME = 'exit_criteria_check'
ANSWER_TOOL = RECORD_EXIT_CHECK_TOOL['name']
SEARCH_TOOL = REQUEST_SEARCH_TOOL['name']
CONTEXT_LIMIT = 3000
JOURNAL_ENTRIES = 3
JOURNAL_ENTRY_LIMIT = 400
QUERY_RULE_LIMIT = 200


@dataclass
class CheckResult:
    status: str
    model_status: str
    summary: str
    web_sources: list
    app_ids: list
    snapshot: list
    searches: int
    tokens_in: int
    tokens_out: int
    cost: float
    no_evidence: bool
    kept_previous: bool
    unresolved_sources: int
    insight: Optional[AIInsight]
    needed_search_but_none_left: bool


def _texts():
    return prompt_service.get_prompt_data(PROMPT_CATEGORY, PROMPT_NAME)


def require_search_capable(model_id):
    """The canonical model id, or ExitWatchError when it cannot search the web."""
    model_id = setup.canonical(model_id)
    if model_id not in SEARCH_CAPABLE:
        raise ExitWatchError(f"{setup.model_label(model_id) or 'That model'} can't search the web. "
                             'Pick Claude or Gemini 3 or later for Exit criteria in Settings → AI.')
    return model_id


def exit_watch_model(user_id):
    """The user's model for Exit criteria (Settings → AI override, else the prompt's `fast`),
    which must be able to search the web and have its provider configured. When the default
    can't search (AI_FAST_MODEL set to one that can't), the first ready search model is used."""
    pref = UserAIPreference.get_preference(user_id, PROMPT_CATEGORY)
    if pref and pref.model_override:
        model_id = require_search_capable(pref.model_override)
    else:
        model_id = setup.canonical(_texts().get('model'))
        if model_id not in SEARCH_CAPABLE or not setup.provider_ready(model_id):
            model_id = require_search_capable(
                next((m for m in SEARCH_CAPABLE if setup.provider_ready(m)), model_id))
    if not setup.provider_ready(model_id):
        provider = setup.PROVIDER_NAMES.get(provider_of(model_id), setup.model_label(model_id))
        raise ExitWatchError(f'{provider} is not configured on the server.')
    return model_id


def _user_context(user, rule, company, texts):
    """The rule's intent for the prompt (never evidence): signal, current thesis, recent notes."""
    parts = [f"{texts['context_signal']}: {rule.title or DEFAULT_SIGNAL}"]
    thesis = current_thesis(user.id, company.id)
    if thesis is not None and (thesis.thesis or '').strip():
        parts.append(f"{texts['context_thesis']}: {thesis.thesis.strip()}")
    entries = JournalEntry.query.filter(
        JournalEntry.user_id == user.id,
        JournalEntry.company_id == company.id,
        JournalEntry.entry_type.notin_(FINDING_TYPES),
        JournalEntry.is_archived.is_(False),
    ).order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()).limit(JOURNAL_ENTRIES).all()
    notes = [finding_text_from_editor(entry.content)[:JOURNAL_ENTRY_LIMIT] for entry in entries]
    notes = [note for note in notes if note.strip()]
    if notes:
        parts.append(f"{texts['context_journal']}:\n" + '\n'.join(f'- {note}' for note in notes))
    return '\n'.join(parts)[:CONTEXT_LIMIT]


def _window_start(previous, rule, now):
    checked = (previous.supporting_data or {}).get('checked_at') if previous is not None else None
    if checked:
        return checked
    created = ensure_timezone_aware(rule.created_at)
    return (created or now).isoformat()


def _source_lines(resolved, texts):
    if not resolved:
        return texts['no_sources']
    return '\n'.join(texts['source_line'].format(
        id=source.id, title=source.title, url=source.url,
        published=source.published.isoformat() if source.published else texts['date_unknown'])
        for source in resolved)


def _search_step(adapter, texts, model_id, base_text, query, searches_left, contact, on_usage):
    """Search, list what came back by id, and ask for the answer citing listed ids only.

    The search step's own answer is never used: its tool call is answered with the ack and the
    listing in the same user turn. Returns (answer, resolved sources, unresolved count).
    """
    cap = min(int(texts['search_cap']), searches_left)
    instruction = texts['search_step_instruction'].format(query=query, search_cap=cap)
    call = stage_call(texts, model_id, f'{base_text}\n\n{instruction}', [RECORD_EXIT_CHECK_TOOL], search_cap=cap)
    reply = adapter.send(call, on_usage)
    resolved, unresolved = sources.resolve_sources(reply.search_results, contact)
    listing = texts['sources_listing'].format(sources=_source_lines(resolved, texts))
    # Claude keeps its search tool so the transcript's search blocks stay valid (the YAML says not
    # to search again); a search it makes anyway is counted, so a rule may use one past the cap.
    used = sum(usage.searches for usage in reply.usages)
    answer_call = replace(call, search_cap=max(1, cap - used))
    transcript = adapter.close_tool_calls(reply.transcript, texts['tool_ack'],
                                          text=f"{listing}\n\n{texts['answer_instruction']}")
    reply = adapter.continue_with(answer_call, transcript, on_usage)
    if reply.tool_name != ANSWER_TOOL:
        reminder = prompt_service.get_prompt('research', 'ai_check_tool_reminder', tool_names=ANSWER_TOOL)
        reply = adapter.follow_up(answer_call, reply.transcript, reminder, on_usage)
        if reply.tool_name != ANSWER_TOOL:
            raise AICheckError(f'The model did not return a result through {ANSWER_TOOL}.')
    return reply.tool_input, resolved, unresolved


def _cited_web_sources(answer, resolved, contact):
    """Cited sources that were listed for this check, each with its best publish date (page dates
    are read here, for the cited sources only)."""
    by_id = {source.id: source for source in resolved}
    sources.add_page_dates(resolved, {c.get('source_id') for c in answer.get('web_sources') or []}, contact)
    cited = []
    for citation in answer.get('web_sources') or []:
        source = by_id.get(citation.get('source_id'))
        if source is None or any(item['id'] == source.id for item in cited):
            continue
        published, date_source = sources.pick_date(source.search_date, source.page_date, citation.get('published'))
        cited.append({'id': source.id, 'url': source.url, 'title': source.title,
                      'published': published.isoformat() if published else None, 'date_source': date_source})
    return cited


def _evidence(decision, previous, summary, web, app_ids, texts, now):
    """What the stored insight shows and cites.

    Normally this check's own summary and citations, also when the verdict kept the previous
    status (a new article for the same status is shown). The previous evidence is carried forward
    only when the previous status was kept and this check either brought no valid citation or
    argued a different status than the kept one (its summary and sources must not appear under
    the kept badge). The rule then still shows why it is at risk or triggered, the next prompt's
    previous summary keeps the reason, and this check's own answer goes in last_news_check.
    """
    own_evidence = bool(web or app_ids) and decision['model_status'] == decision['status']
    if not decision['kept_previous'] or previous is None or own_evidence:
        text = texts['no_evidence_summary'] if decision['no_evidence'] or not summary else summary
        return {'insight_text': text, 'summary': summary, 'web_sources': web, 'app_figures_cited': app_ids,
                'extra': {}}
    data = previous.supporting_data or {}
    cited = set(data.get('app_figures_cited') or [])
    return {
        'insight_text': previous.insight_text,
        'summary': data.get('summary') or previous.insight_text,
        'web_sources': data.get('web_sources') or [],
        'app_figures_cited': data.get('app_figures_cited') or [],
        'extra': {
            'evidence_carried': True,
            # "Nothing new since <evidence_checked_at>"
            'evidence_checked_at': data.get('evidence_checked_at') or data.get('checked_at'),
            'evidence_snapshot': data.get('evidence_snapshot') or [
                item for item in data.get('snapshot') or [] if item.get('id') in cited],
            'last_news_check': {'checked_at': now.isoformat(), 'model_status': decision['model_status'],
                                'summary': summary, 'web_sources': web, 'app_figures_cited': app_ids},
        },
    }


def _store(user, rule, company, adapter, model_id, decision, evidence, snapshot, tally, window_start, now,
           expires_after):
    AIInsight.query.filter(
        AIInsight.user_id == user.id,
        AIInsight.context_type == CONTEXT_TYPE,
        AIInsight.context_id == rule.id,
        AIInsight.is_active.is_(True),
    ).update({'is_active': False}, synchronize_session='fetch')
    status = decision['status']
    insight = AIInsight(
        user_id=user.id,
        insight_type='reminder' if status == 'intact' else 'warning',
        trigger_type='periodic',
        context_type=CONTEXT_TYPE,
        context_id=rule.id,
        company_id=company.id,
        title=f'{rule.title or DEFAULT_SIGNAL}: {STATUS_LABELS[status]}'[:200],
        insight_text=evidence['insight_text'],
        supporting_data={
            'status': status, 'model_status': decision['model_status'],
            'no_evidence': decision['no_evidence'], 'kept_previous': decision['kept_previous'],
            'summary': evidence['summary'], 'web_sources': evidence['web_sources'],
            'app_figures_cited': evidence['app_figures_cited'], 'snapshot': snapshot,
            'searches': tally.web_searches, 'window_start': window_start, 'checked_at': now.isoformat(),
            'model': model_id, **evidence['extra'],
        },
        confidence=None,
        ai_provider=adapter.provider,
        model_version=model_id,
        is_active=True,
        expires_at=now + expires_after,
    )
    db.session.add(insight)
    db.session.flush()
    return insight


def _decide(answer, web_ids, app_ids, previous_status):
    model_status = answer.get('status') if answer.get('status') in STATUS_LABELS else 'intact'
    return verdict.decide(model_status, bool(answer.get('changed')), web_ids, app_ids, previous_status)


def _needs_search(name, answer, snapshot, previous_status):
    """Whether step A's reply is treated as a search request.

    A zero-search answer must rest on app figures. And a rule that is at risk or triggered only
    goes down on a search: a zero-search answer that would lower its status goes to search too
    (one that keeps or raises it on app figures is fine).
    """
    if name != ANSWER_TOOL:
        return True
    app_ids = figures.valid_app_citations(answer.get('app_figures'), snapshot)
    if not app_ids:
        return True
    if previous_status in ('at_risk', 'triggered'):
        status = _decide(answer, [], app_ids, previous_status)['status']
        return STATUS_RANK[status] < STATUS_RANK[previous_status]
    return False


def _run_check(user, rule, position, company, adapter, model_id, searches_left, previous, contact,
               expires_after, now, service, texts, tally):
    def on_usage(usage):
        record_usage(tally, usage)

    def result(**values):
        return CheckResult(searches=tally.web_searches, tokens_in=tally.tokens_in, tokens_out=tally.tokens_out,
                           cost=tally.cost_estimate, **values)

    snapshot = figures.build_snapshot(position, company, service=service, now=now)
    window_start = _window_start(previous, rule, now)
    previous_status = (previous.supporting_data or {}).get('status') if previous is not None else None
    variables = {
        'company_name': company.name, 'ticker': company.ticker_symbol or '',
        'rule_signal': rule.title or DEFAULT_SIGNAL, 'rule_text': finding_text_from_editor(rule.content),
        'window_start': window_start[:10], 'today': now.date().isoformat(),
        'previous_status': previous_status or texts['no_previous'],
        'previous_summary': previous.insight_text if previous is not None else texts['no_previous'],
        'user_context': _user_context(user, rule, company, texts),
        'app_figures': figures.snapshot_text(snapshot),
    }
    base_text = texts['template'].format(**variables)

    step_a = stage_call(texts, model_id, f"{base_text}\n\n{texts['answer_or_search_instruction']}",
                        [RECORD_EXIT_CHECK_TOOL, REQUEST_SEARCH_TOOL])
    name, answer, _ = call_for_tool(adapter, step_a, {ANSWER_TOOL, SEARCH_TOOL}, on_usage)
    resolved, unresolved = [], 0
    if _needs_search(name, answer, snapshot, previous_status):
        if searches_left <= 0:
            return result(status=previous_status or '', model_status='', summary='', web_sources=[], app_ids=[],
                          snapshot=snapshot, no_evidence=False, kept_previous=False, unresolved_sources=0,
                          insight=None, needed_search_but_none_left=True)
        query = (answer.get('query') or '').strip() if name == SEARCH_TOOL else ''
        query = query or texts['fallback_query'].format(
            **{**variables, 'rule_text': variables['rule_text'][:QUERY_RULE_LIMIT]})
        answer, resolved, unresolved = _search_step(adapter, texts, model_id, base_text, query, searches_left,
                                                    contact, on_usage)

    web = _cited_web_sources(answer, resolved, contact)
    app_ids = figures.valid_app_citations(answer.get('app_figures'), snapshot)
    decision = _decide(answer, [item['id'] for item in web], app_ids, previous_status)
    summary = (answer.get('summary') or '').strip()
    evidence = _evidence(decision, previous, summary, web, app_ids, texts, now)
    insight = _store(user, rule, company, adapter, model_id, decision, evidence, snapshot, tally, window_start,
                     now, expires_after)
    return result(status=decision['status'], model_status=decision['model_status'], summary=evidence['summary'],
                  web_sources=evidence['web_sources'], app_ids=evidence['app_figures_cited'], snapshot=snapshot,
                  no_evidence=decision['no_evidence'], kept_previous=decision['kept_previous'],
                  unresolved_sources=unresolved, insight=insight, needed_search_but_none_left=False)


def check_rule(user, rule, position, company, adapter, model_id, searches_left, previous, contact,
               expires_after, now=None, service=None):
    """Check one must-exit rule and store the result as the rule's one active AIInsight.

    `searches_left` is the user's remaining search allowance (the caller reads it), `previous` the
    rule's latest exit_criterion insight, active or not (None before the first check), `contact`
    the fetcher's AI_CHECK_FETCH_CONTACT. Returns a CheckResult; `needed_search_but_none_left`
    means no insight was stored.

    Every call writes one PromptUsageLog row with the tokens and searches spent, also when a step
    raises, and charges the tokens to the user. On success the insight, the charge and the log row
    are committed together (log_prompt_usage commits). On failure the session is rolled back first,
    so the partial insight is never committed, and the exception is re-raised. That rollback also
    drops anything else pending in the session: the caller must commit before each rule.
    """
    now = now or now_utc()
    texts = _texts()
    tally = UsageTally()
    rule_id = rule.id  # read before any rollback expires the row
    try:
        outcome = _run_check(user, rule, position, company, adapter, model_id, searches_left, previous, contact,
                             expires_after, now, service, texts, tally)
    except Exception as exc:
        db.session.rollback()
        try:
            _charge_and_log(user, rule, adapter, model_id, texts, tally, success=False,
                            error=str(exc) or type(exc).__name__)
        except SoftTimeLimitExceeded:
            raise
        except Exception:  # never mask the check's own error
            LOG.exception('exit watch: could not log the failed check of rule %s', rule_id)
            db.session.rollback()
        raise
    if _charge_and_log(user, rule, adapter, model_id, texts, tally, success=True) is None:
        raise ExitWatchError('The exit-criteria check could not be saved.')
    return outcome


def _charge_and_log(user, rule, adapter, model_id, texts, tally, success, error=None):
    user.increment_ai_tokens(tally.tokens_in + tally.tokens_out, commit=False)
    return log_prompt_usage(
        PROMPT_NAME, str(texts.get('version') or ''), adapter.provider, model_id,
        input_tokens=tally.tokens_in, output_tokens=tally.tokens_out, success=success, error_message=error,
        context_data={'rule_id': rule.id}, user_id=user.id, web_searches=tally.web_searches,
        cost_dollars=tally.cost_estimate)
