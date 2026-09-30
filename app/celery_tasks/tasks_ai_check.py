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

"""Celery tasks for the AI check: Gather → (Extract × N, in parallel) → Analyze, plus the reaper."""

import logging

from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded
from flask import current_app

from app import create_app, db
from app.models import AICheckRun, AICheckSource
from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai_check import AICheckError
from app.services.ai_check.pipeline import (
    do_analyze, do_extract, do_gather, mark_failed, reap_stale_runs,
)
from celery_app import celery

logger = logging.getLogger(__name__)

GATHER_SOFT_LIMIT = 300
EXTRACT_SOFT_LIMIT = 240
ANALYZE_SOFT_LIMIT = 300
RETRY_COUNTDOWN = 15


def claude_available():
    return ClaudeProvider().is_available()


def create_message_for_run():
    provider = ClaudeProvider()
    if not provider.is_available():
        raise AICheckError('Claude is not configured on the server.')
    return provider.create_message


def dispatch_extract_and_analyze(run_id, source_ids):
    chord(group(ai_check_extract_task.s(sid) for sid in source_ids))(ai_check_analyze_task.s(run_id))


def _fail_run(run_id, stage, message):
    db.session.rollback()
    run = db.session.get(AICheckRun, run_id)
    if run is not None and not run.is_terminal:
        mark_failed(run, stage, message)


def _extract_failed(source_id, message):
    db.session.rollback()
    source = db.session.get(AICheckSource, source_id)
    if source is not None and source.extract_status != 'done':
        source.extract_status, source.error = 'failed', message[:2000]
        db.session.commit()


def _gather(run_id, gaps, final_attempt):
    """Runs the Gather stage, then queues the next step. Queueing failures (a broker error
    after the stage already committed) fail the run outright and are never retried -- retrying
    here would re-run Gather (a second paid web search, duplicate source rows) even though
    Gather itself already succeeded."""
    if not claude_available():
        _fail_run(run_id, 'gathering', 'Claude is not configured on the server.')
        return
    source_ids = do_gather(run_id, create_message_for_run(), gaps=gaps, final_attempt=final_attempt)
    run = db.session.get(AICheckRun, run_id)
    if run is None or run.is_terminal:
        return
    try:
        if source_ids:
            dispatch_extract_and_analyze(run_id, source_ids)
        else:
            ai_check_analyze_task.delay(None, run_id)
    except Exception as exc:
        _fail_run(run_id, 'gathering', f'Could not queue the next step: {exc}')


def _after_analyze(run_id, outcome):
    """Queues Gather again on a loop-back. As in _gather, a queueing failure here fails the
    run rather than being retried, since Analyze itself already committed its result."""
    if outcome.get('action') != 'loop_back':
        return
    try:
        ai_check_gather_task.delay(run_id, gaps=outcome.get('gaps'))
    except Exception as exc:
        _fail_run(run_id, 'analyzing', f'Could not queue the next step: {exc}')


@celery.task(bind=True, max_retries=1, soft_time_limit=GATHER_SOFT_LIMIT,
             time_limit=GATHER_SOFT_LIMIT + 30)
def ai_check_gather_task(self, run_id, gaps=None):
    app = create_app()
    with app.app_context():
        final = self.request.retries >= self.max_retries
        try:
            _gather(run_id, gaps, final_attempt=final)
        except SoftTimeLimitExceeded:
            _fail_run(run_id, 'gathering', 'Gathering sources took too long.')
        except AICheckError as exc:
            _fail_run(run_id, 'gathering', str(exc))
        except Exception as exc:  # transient: do_gather re-raised on a non-final attempt
            if final:
                _fail_run(run_id, 'gathering', f'Gathering failed: {exc}')
                return
            logger.warning('AI check gather %s retrying: %s', run_id, exc)
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN)


@celery.task(bind=True, max_retries=1, soft_time_limit=EXTRACT_SOFT_LIMIT,
             time_limit=EXTRACT_SOFT_LIMIT + 30)
def ai_check_extract_task(self, source_id):
    """Never raises after its last attempt, so the chord always reaches Analyze."""
    app = create_app()
    with app.app_context():
        final = self.request.retries >= self.max_retries
        try:
            do_extract(source_id, create_message_for_run(), current_app.config['UPLOAD_FOLDER'],
                       final_attempt=final)
        except SoftTimeLimitExceeded:
            _extract_failed(source_id, 'Reading this source took too long.')
        except AICheckError as exc:
            _extract_failed(source_id, str(exc))
        except Exception as exc:
            if final:
                _extract_failed(source_id, f'Extraction failed: {exc}')
            else:
                raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN)
    return source_id


@celery.task(bind=True, max_retries=1, soft_time_limit=ANALYZE_SOFT_LIMIT,
             time_limit=ANALYZE_SOFT_LIMIT + 30)
def ai_check_analyze_task(self, _results, run_id):
    app = create_app()
    with app.app_context():
        final = self.request.retries >= self.max_retries
        try:
            outcome = do_analyze(run_id, create_message_for_run(), final_attempt=final)
        except SoftTimeLimitExceeded:
            _fail_run(run_id, 'analyzing', 'The analysis took too long.')
            return
        except AICheckError as exc:
            _fail_run(run_id, 'analyzing', str(exc))
            return
        except Exception as exc:
            if final:
                _fail_run(run_id, 'analyzing', f'Analysis failed: {exc}')
                return
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN)
        _after_analyze(run_id, outcome)


@celery.task
def ai_check_reap_task():
    app = create_app()
    with app.app_context():
        count = reap_stale_runs()
        if count:
            logger.info('AI check reaper failed %d stale run(s)', count)
        return count
