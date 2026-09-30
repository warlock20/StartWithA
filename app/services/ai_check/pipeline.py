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

"""Run lifecycle for the AI check: start, stage steps with error policy, retry, cancel, reap, JSON."""

from datetime import timedelta

from sqlalchemy import func

from app import db
from app.models import AICheckRun, AICheckSource, CompanyResource, User
from app.services.ai_check import AICheckError
from app.services.ai_check.context import context_snapshot, has_ai_context
from app.services.ai_check.llm import UsageTally
from app.services.ai_check.stages import (
    MAX_SOURCES, create_document_sources, run_analyze, run_extract, run_gather, usage_tally,
)
from app.utils.time_utils import now_utc

STALE_AFTER = timedelta(minutes=30)
STAGE_STATUS = {'gathering': 'gathering', 'extracting': 'extracting', 'analyzing': 'analyzing'}
USAGE_FIELDS = ('tokens_in', 'tokens_out', 'cache_read_tokens', 'web_searches', 'web_fetches', 'cost_estimate')


def active_run_for(user_id, company_id, item_id):
    return AICheckRun.query.filter(
        AICheckRun.user_id == user_id, AICheckRun.company_id == company_id,
        AICheckRun.checklist_item_id == item_id,
        AICheckRun.status.notin_(AICheckRun.TERMINAL_STATUSES),
    ).order_by(AICheckRun.id.desc()).first()


def _document_ids(user_id, company_id, mode, raw_ids):
    if mode == 'web':
        return []
    try:
        ids = sorted({int(value) for value in raw_ids or []})
    except (TypeError, ValueError):
        raise AICheckError('Invalid document id.')
    if mode == 'documents' and not ids:
        raise AICheckError('Pick at least one document.')
    if len(ids) > MAX_SOURCES:
        raise AICheckError(f'Pick at most {MAX_SOURCES} documents.')
    owned = CompanyResource.query.filter(
        CompanyResource.id.in_(ids), CompanyResource.company_id == company_id,
        CompanyResource.user_id == user_id, CompanyResource.resource_type == 'file',
    ).count() if ids else 0
    if owned != len(ids):
        raise AICheckError('One or more documents are not available for this company.')
    return ids


def start_run(user_id, analysis, item, mode, document_ids):
    if mode not in AICheckRun.MODES:
        raise AICheckError('Unknown source mode.')
    if not has_ai_context(item.ai_context):
        raise AICheckError('This question has no AI context yet.')
    active = active_run_for(user_id, analysis.company_id, item.id)
    if active:
        return active, False
    run = AICheckRun(
        user_id=user_id, company_id=analysis.company_id, checklist_item_id=item.id,
        analysis_id=analysis.id, mode=mode,
        document_ids=_document_ids(user_id, analysis.company_id, mode, document_ids),
        context_snapshot=context_snapshot(item), status='queued', models={},
    )
    db.session.add(run)
    db.session.commit()
    return run, True


def _apply_usage(run_id, user_id, tally):
    """Add one stage attempt's usage tally to the run and the user as atomic SQL-side
    increments, so two writers touching the same row never lose each other's usage. The tally
    is a plain (non-mapped) object -- see stages.usage_tally -- so the run's own ORM columns
    are never touched by stage code, and there is nothing for an intervening autoflush to
    write ahead of this update. Doesn't commit; the caller commits. Skips both updates when
    the tally is all zeros."""
    if not any(getattr(tally, field) for field in USAGE_FIELDS):
        return
    AICheckRun.query.filter_by(id=run_id).update(
        {getattr(AICheckRun, field): getattr(AICheckRun, field) + getattr(tally, field)
         for field in USAGE_FIELDS},
        synchronize_session=False)
    tokens_delta = tally.tokens_in + tally.tokens_out
    if tokens_delta:
        User.query.filter_by(id=user_id).update(
            {User.ai_tokens_used: User.ai_tokens_used + tokens_delta}, synchronize_session=False)


def mark_failed(run, stage, message):
    run.status, run.failed_stage = 'failed', stage
    run.error = (message or 'Unknown error')[:2000]
    run.completed_at = now_utc()
    db.session.commit()


def cancel_run(run):
    if run.is_terminal:
        return
    run.status, run.completed_at = 'cancelled', now_utc()
    db.session.commit()


def _live_run(run_id):
    run = db.session.get(AICheckRun, run_id)
    return None if run is None or run.is_terminal else run


def queued_source_ids(run):
    return [s.id for s in run.sources if s.extract_status == 'queued']


def do_gather(run_id, create_message, gaps=None, final_attempt=True):
    run = _live_run(run_id)
    if run is None:
        return []
    run_id, user_id = run.id, run.user_id
    run.status = 'gathering'
    run.started_at = run.started_at or now_utc()
    run.models = {**(run.models or {}), 'gather': 'claude-sonnet-5'}
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        if gaps is None and run.document_ids and not run.sources:
            create_document_sources(run)
        if run.mode in ('web', 'both'):
            run_gather(run, create_message, gaps)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', str(exc))
        return []
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', f'Gathering failed: {exc}')
        return []

    tally = usage_tally(run)

    live_status = db.session.query(AICheckRun.status).filter(AICheckRun.id == run_id).scalar()
    if live_status in AICheckRun.TERMINAL_STATUSES:
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        return []

    if gaps is None and not run.sources:
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', 'No sources were found for this question.')
        return []

    _apply_usage(run_id, user_id, tally)
    run.status = 'extracting'
    db.session.commit()
    return queued_source_ids(run)


def do_extract(source_id, create_message, upload_folder, final_attempt=True):
    source = db.session.get(AICheckSource, source_id)
    if source is None or source.run.is_terminal:
        return
    run = source.run
    run_id, user_id = run.id, run.user_id
    source.extract_status, source.error = 'running', None
    run.models = {**(run.models or {}), 'extract': 'claude-sonnet-5'}
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        evidence = run_extract(source, create_message, upload_folder)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        _fail_source(source_id, str(exc))
        return
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        _fail_source(source_id, f'Extraction failed: {exc}')
        return
    tally = usage_tally(run)
    _apply_usage(run_id, user_id, tally)
    source.extract_status = 'done' if evidence else 'no_figures'
    db.session.commit()


def _fail_source(source_id, message):
    source = db.session.get(AICheckSource, source_id)
    source.extract_status, source.error = 'failed', message[:2000]
    db.session.commit()


def do_analyze(run_id, create_message, final_attempt=True):
    run = _live_run(run_id)
    if run is None:
        return {'action': 'stop'}
    run_id, user_id = run.id, run.user_id
    if not run.evidence:
        failed_count = sum(1 for s in run.sources if s.extract_status == 'failed')
        if failed_count:
            mark_failed(run, 'extracting',
                        f'No figures were found: {failed_count} source(s) could not be read. '
                        'Retry to read them again.')
        else:
            mark_failed(run, 'analyzing', 'No figures were found in any source.')
        return {'action': 'stop'}
    run.status = 'analyzing'
    run.models = {**(run.models or {}), 'analyze': 'claude-opus-5'}
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        outcome, payload = run_analyze(run, create_message)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', str(exc))
        return {'action': 'stop'}
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', f'Analysis failed: {exc}')
        return {'action': 'stop'}

    tally = usage_tally(run)

    live_status = db.session.query(AICheckRun.status).filter(AICheckRun.id == run_id).scalar()
    if live_status in AICheckRun.TERMINAL_STATUSES:
        db.session.rollback()
        _apply_usage(run_id, user_id, tally)
        db.session.commit()
        return {'action': 'stop'}

    if outcome == 'more_evidence':
        _apply_usage(run_id, user_id, tally)
        run.loop_back_used, run.status = True, 'gathering'
        run.started_at = now_utc()  # a new pass begins; started_at marks the current pass, not run creation
        db.session.commit()
        return {'action': 'loop_back', 'gaps': payload}

    _apply_usage(run_id, user_id, tally)
    run.result, run.status, run.completed_at = payload, 'completed', now_utc()
    db.session.commit()
    return {'action': 'done'}


def retry_run(run):
    if run.status != 'failed' or run.failed_stage not in STAGE_STATUS:
        raise AICheckError('Only a failed run can be retried.')
    stage = run.failed_stage
    if stage == 'extracting':
        for source in run.sources:
            if source.extract_status in ('failed', 'running'):
                source.extract_status, source.error = 'queued', None
    run.status, run.failed_stage, run.error, run.completed_at = STAGE_STATUS[stage], None, None, None
    run.started_at = now_utc()  # a new pass begins; started_at marks the current pass, not run creation
    db.session.commit()
    return stage, (queued_source_ids(run) if stage == 'extracting' else [])


def reap_stale_runs(now=None):
    cutoff = (now or now_utc()) - STALE_AFTER
    stale = AICheckRun.query.filter(
        AICheckRun.status.notin_(AICheckRun.TERMINAL_STATUSES),
        func.coalesce(AICheckRun.started_at, AICheckRun.created_at) < cutoff).all()
    for run in stale:
        run.status, run.failed_stage = 'failed', run.status
        run.error, run.completed_at = 'The run took too long and was stopped.', now_utc()
    db.session.commit()
    return len(stale)


def _iso(value):
    return value.isoformat() if value else None


def serialize_run(run):
    return {
        'id': run.id, 'status': run.status, 'mode': run.mode,
        'failed_stage': run.failed_stage, 'error': run.error,
        'created_at': _iso(run.created_at), 'completed_at': _iso(run.completed_at),
        'loop_back_used': run.loop_back_used, 'cost_estimate': round(run.cost_estimate or 0.0, 4),
        'sources': [{
            'id': s.id, 'kind': s.kind, 'title': s.title, 'url': s.url, 'doc_type': s.doc_type,
            'period': s.period, 'gap_filled': s.gap_filled, 'extract_status': s.extract_status,
            'error': s.error, 'evidence_count': len(s.evidence),
        } for s in run.sources],
        'evidence': [{
            'label': e.label, 'metric': e.metric, 'value': e.value, 'unit': e.unit,
            'period': e.period, 'location': e.location, 'quote': e.quote, 'verified': e.verified,
            'source_title': e.source.title, 'source_url': e.source.url, 'source_kind': e.source.kind,
        } for e in sorted(run.evidence, key=lambda e: e.id)],
        'result': run.result,
    }


def serialize_history(runs):
    return [{'id': r.id, 'status': r.status, 'mode': r.mode, 'created_at': _iso(r.created_at),
             'suggested_verdict': (r.result or {}).get('suggested_verdict')} for r in runs]
