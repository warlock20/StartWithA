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

from flask import current_app
from sqlalchemy import func

from app import db
from app.models import AICheckRun, AICheckSource, CompanyResource
from app.services.ai_check import AICheckError, AICheckRunLimitError
from app.services.ai_check.context import context_snapshot, has_ai_context
from app.services.ai_check.fetch import clear_run_files, sweep_run_files
from app.services.ai_check.pricing import provider_of
from app.services.ai_check.setup import resolve_setup, setup_summary, user_search_budget
from app.services.ai_check.llm import UsageTally
from app.services.ai_check.stages import (
    MAX_SOURCES, create_document_sources, run_analyze, run_extract, run_gather, run_quick, usage_tally,
)
from app.utils.time_utils import ensure_timezone_aware, now_utc

STALE_AFTER = timedelta(minutes=30)
FAILED_FILES_KEPT_FOR = timedelta(days=7)  # a failed run keeps its downloads so Retry reuses them
RUN_LIMIT_WINDOW = timedelta(days=30)
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


def _downloads_web_pages(models):
    """True when Extract reads web sources from our own download (not Claude's web_fetch)."""
    return not (provider_of(models['extract']) == 'claude'
                and current_app.config.get('AI_CHECK_CLAUDE_WEB_FETCH', True))


def runs_in_window(user_id, now=None):
    since = (now or now_utc()) - RUN_LIMIT_WINDOW
    return AICheckRun.query.filter(AICheckRun.user_id == user_id, AICheckRun.created_at >= since).count()


def start_run(user_id, analysis, item, mode, document_ids, run_limit=None, setup_choice=None, depth='full'):
    """Return (run, created). An active run for the same question is returned as is; a new run
    is refused with AICheckRunLimitError once the user has started `run_limit` runs in the last
    30 days (None = no cap; the route passes AI_CHECK_MONTHLY_RUN_LIMIT). `setup_choice` is a
    preset key or 'my_setup' (None = 'my_setup'); the resolved per-stage models are frozen on the run.
    `depth` is 'full' (Gather → Extract → Analyze) or 'quick' (one call)."""
    reap_stale_runs()
    if mode not in AICheckRun.MODES:
        raise AICheckError('Unknown source mode.')
    if depth not in AICheckRun.DEPTHS:
        raise AICheckError('Unknown depth.')
    if not has_ai_context(item.ai_context):
        raise AICheckError('This question has no AI context yet.')
    active = active_run_for(user_id, analysis.company_id, item.id)
    if active:
        return active, False
    if run_limit is not None and runs_in_window(user_id) >= run_limit:
        raise AICheckRunLimitError(f'You have used all {run_limit} AI checks for the last 30 days.')
    models = {**resolve_setup(user_id, setup_choice), 'search_budget': user_search_budget(user_id)}
    if depth == 'full' and mode != 'documents' and _downloads_web_pages(models) \
            and not current_app.config.get('AI_CHECK_FETCH_CONTACT'):
        # Refuse before Gather is paid for: every web source would fail at Extract.
        raise AICheckError('Web fetching is not configured on the server (AI_CHECK_FETCH_CONTACT). '
                           'Use My documents, a Claude setup, or Quick.')
    run = AICheckRun(
        user_id=user_id, company_id=analysis.company_id, checklist_item_id=item.id,
        analysis_id=analysis.id, mode=mode, depth=depth,
        document_ids=_document_ids(user_id, analysis.company_id, mode, document_ids),
        context_snapshot=context_snapshot(item), status='queued', models=models,
    )
    db.session.add(run)
    db.session.commit()
    return run, True


def _apply_usage(run_id, tally):
    """Add one stage attempt's usage tally to the run as atomic SQL-side increments, so two writers touching the same row never lose each other's usage. The tally
    is a plain (non-mapped) object -- see stages.usage_tally -- so the run's own ORM columns
    are never touched by stage code, and there is nothing for an intervening autoflush to
    write ahead of this update. Doesn't commit; the caller commits. Skips the update when
    the tally is all zeros. AI check usage is NOT charged to User.ai_tokens_used: runs are capped
    by count instead (AI_CHECK_MONTHLY_RUN_LIMIT, see start_run)."""
    if not any(getattr(tally, field) for field in USAGE_FIELDS):
        return
    AICheckRun.query.filter_by(id=run_id).update(
        {getattr(AICheckRun, field): getattr(AICheckRun, field) + getattr(tally, field)
         for field in USAGE_FIELDS},
        synchronize_session=False)


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
    _clear_files(run.id)


def _clear_files(run_id):
    clear_run_files(current_app.config['UPLOAD_FOLDER'], run_id)


def sweep_stale_run_files(now=None):
    """Delete downloaded web sources of runs that no longer need them: completed, cancelled,
    failed more than FAILED_FILES_KEPT_FOR ago, or deleted. Returns how many folders went."""
    cutoff = (now or now_utc()) - FAILED_FILES_KEPT_FOR

    def keep(run_id):
        run = db.session.get(AICheckRun, run_id)
        if run is None or run.status in ('completed', 'cancelled'):
            return False
        return run.status != 'failed' or ensure_timezone_aware(run.completed_at or now_utc()) >= cutoff
    return sweep_run_files(current_app.config['UPLOAD_FOLDER'], keep)


def _live_run(run_id):
    run = db.session.get(AICheckRun, run_id)
    return None if run is None or run.is_terminal else run


def queued_source_ids(run):
    return [s.id for s in run.sources if s.extract_status == 'queued']


def do_gather(run_id, adapter, gaps=None, final_attempt=True):
    run = _live_run(run_id)
    if run is None:
        return []
    run_id = run.id
    run.status = 'gathering'
    run.started_at = run.started_at or now_utc()
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        if gaps is None and run.document_ids and not run.sources:
            create_document_sources(run)
        if run.mode in ('web', 'both'):
            run_gather(run, adapter, gaps)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', str(exc))
        return []
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', f'Gathering failed: {exc}')
        return []

    tally = usage_tally(run)

    live_status = db.session.query(AICheckRun.status).filter(AICheckRun.id == run_id).scalar()
    if live_status in AICheckRun.TERMINAL_STATUSES:
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        return []

    if gaps is None and not run.sources:
        _apply_usage(run_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'gathering', 'No sources were found for this question.')
        return []

    _apply_usage(run_id, tally)
    run.status = 'extracting'
    db.session.commit()
    return queued_source_ids(run)


def do_extract(source_id, adapter, upload_folder, final_attempt=True):
    source = db.session.get(AICheckSource, source_id)
    if source is None or source.run.is_terminal:
        return
    run = source.run
    run_id = run.id
    source.extract_status, source.error = 'running', None
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        evidence = run_extract(source, adapter, upload_folder)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        _fail_source(source_id, str(exc))
        return
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        _fail_source(source_id, f'Extraction failed: {exc}')
        return
    tally = usage_tally(run)
    _apply_usage(run_id, tally)
    source.extract_status = 'done' if evidence else 'no_figures'
    db.session.commit()


def _fail_source(source_id, message):
    source = db.session.get(AICheckSource, source_id)
    source.extract_status, source.error = 'failed', message[:2000]
    db.session.commit()


def do_analyze(run_id, adapter, final_attempt=True):
    run = _live_run(run_id)
    if run is None:
        return {'action': 'stop'}
    run_id = run.id
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
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        outcome, payload = run_analyze(run, adapter)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', str(exc))
        return {'action': 'stop'}
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', f'Analysis failed: {exc}')
        return {'action': 'stop'}

    tally = usage_tally(run)

    live_status = db.session.query(AICheckRun.status).filter(AICheckRun.id == run_id).scalar()
    if live_status in AICheckRun.TERMINAL_STATUSES:
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        return {'action': 'stop'}

    if outcome == 'more_evidence':
        _apply_usage(run_id, tally)
        run.loop_back_used, run.status = True, 'gathering'
        run.started_at = now_utc()  # a new pass begins; started_at marks the current pass, not run creation
        db.session.commit()
        return {'action': 'loop_back', 'gaps': payload}

    _apply_usage(run_id, tally)
    run.result, run.status, run.completed_at = payload, 'completed', now_utc()
    db.session.commit()
    _clear_files(run_id)
    return {'action': 'done'}


def do_quick(run_id, adapter, upload_folder, final_attempt=True):
    """The Quick check's single call. Fails at 'analyzing', so Retry re-runs this call."""
    run = _live_run(run_id)
    if run is None:
        return {'action': 'stop'}
    run_id = run.id
    run.status = 'analyzing'
    run.started_at = run.started_at or now_utc()
    db.session.commit()
    run._ai_usage_tally = UsageTally()
    try:
        result = run_quick(run, adapter, upload_folder)
    except AICheckError as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', str(exc))
        return {'action': 'stop'}
    except Exception as exc:
        tally = usage_tally(run)
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        if not final_attempt:
            raise
        mark_failed(db.session.get(AICheckRun, run_id), 'analyzing', f'Quick check failed: {exc}')
        return {'action': 'stop'}

    tally = usage_tally(run)
    live_status = db.session.query(AICheckRun.status).filter(AICheckRun.id == run_id).scalar()
    if live_status in AICheckRun.TERMINAL_STATUSES:
        db.session.rollback()
        _apply_usage(run_id, tally)
        db.session.commit()
        return {'action': 'stop'}
    _apply_usage(run_id, tally)
    run.result, run.status, run.completed_at = result, 'completed', now_utc()
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
    """Fail runs stuck in a non-terminal status past STALE_AFTER. Cheap enough to call
    opportunistically (start, status, history) as well as from beat; commits only when it reaps."""
    cutoff = (now or now_utc()) - STALE_AFTER
    stale = AICheckRun.query.filter(
        AICheckRun.status.notin_(AICheckRun.TERMINAL_STATUSES),
        func.coalesce(AICheckRun.started_at, AICheckRun.created_at) < cutoff).all()
    for run in stale:
        run.status, run.failed_stage = 'failed', run.status
        run.error, run.completed_at = 'The run took too long and was stopped.', now_utc()
    if stale:
        db.session.commit()
    return len(stale)


def _iso(value):
    return value.isoformat() if value else None


def serialize_run(run):
    return {
        'id': run.id, 'status': run.status, 'mode': run.mode, 'depth': run.depth,
        'setup': setup_summary(run),
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
    return [{'id': r.id, 'status': r.status, 'mode': r.mode, 'depth': r.depth, 'setup': setup_summary(r),
             'created_at': _iso(r.created_at),
             'suggested_verdict': (r.result or {}).get('suggested_verdict')} for r in runs]
