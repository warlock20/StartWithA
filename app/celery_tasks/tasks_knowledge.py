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

"""
Companion knowledge index tasks.

The nightly beat job queues one small task per user (staggered, so a first
backfill doesn't hit provider rate limits all at once). A user's task writes a
BackgroundTask row only when there is work to do or the run fails, so the
settings page shows real runs without a row per user per night.

Re-index now (settings) queues reindex_knowledge_task through
BackgroundTaskService, which creates the row up front.
"""

import json
import logging
import uuid
from contextlib import nullcontext
from dataclasses import asdict
from datetime import timedelta

from celery.exceptions import SoftTimeLimitExceeded
from flask import has_app_context
from sqlalchemy import exists, or_

from app import create_app, db
from app.celery_tasks.base import GENERIC_FAILURE, TaskFailed, background_task, record_job_run
from app.models import BackgroundTask, User
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.argos.knowledge_index import TASK_TYPE, IndexUnavailable, index_user_knowledge
from app.utils.time_utils import now_utc
from celery_app import celery

logger = logging.getLogger(__name__)

NIGHTLY_JOB = 'knowledge-index-nightly'
STAGGER_SECONDS = 15
SOFT_TIME_LIMIT = 600
TIMEOUT_MESSAGE = f'Timed out after {SOFT_TIME_LIMIT}s. The next run continues where this one stopped.'


@celery.task
@record_job_run(NIGHTLY_JOB)
def index_all_knowledge():
    """Queue a knowledge index run for every user with AI consent or with chunks left to remove."""
    has_chunks = exists().where(KnowledgeChunk.user_id == User.id)
    user_ids = [user_id for (user_id,) in db.session.query(User.id).filter(
        or_(User.ai_consent_given.is_(True), has_chunks)).order_by(User.id)]
    for position, user_id in enumerate(user_ids):
        index_user_knowledge_task.apply_async(args=(user_id,), countdown=position * STAGGER_SECONDS)
    logger.info(f"Knowledge index: queued {len(user_ids)} user(s)")
    return {'users_queued': len(user_ids)}


@celery.task(bind=True, soft_time_limit=SOFT_TIME_LIMIT)
def index_user_knowledge_task(self, user_id):
    """One user's scheduled run. Skips a user whose run (scheduled or manual) is still going."""
    with nullcontext() if has_app_context() else create_app().app_context():
        if _run_in_progress(user_id):
            logger.info(f"Knowledge index for user {user_id} skipped: a run is in progress")
            return {'status': 'skipped'}

        row_ids = []
        try:
            run = index_user_knowledge(user_id, on_work=lambda count: row_ids.append(_start_row(user_id)))
        except IndexUnavailable as e:
            return _fail(user_id, row_ids, str(e))
        except SoftTimeLimitExceeded:
            logger.error(f"Knowledge index for user {user_id} hit its {SOFT_TIME_LIMIT}s soft time limit")
            return _fail(user_id, row_ids, TIMEOUT_MESSAGE)
        except Exception:
            logger.exception(f"Knowledge index for user {user_id} failed")
            return _fail(user_id, row_ids, GENERIC_FAILURE)

        result = asdict(run)
        if row_ids:
            row = db.session.get(BackgroundTask, row_ids[0])
            row.status = 'completed'
            row.completed_at = now_utc()
            row.result = json.dumps(result)
            db.session.commit()
        return {'status': 'completed', **result}


@background_task(soft_time_limit=SOFT_TIME_LIMIT, timeout_message=TIMEOUT_MESSAGE)
def reindex_knowledge_task(self, task, user_id):
    """Re-index now from settings: the same incremental run, tracked on its own BackgroundTask row."""
    try:
        return asdict(index_user_knowledge(user_id))
    except IndexUnavailable as e:
        raise TaskFailed(str(e)) from e


def _run_in_progress(user_id):
    """A knowledge_index row still pending or running. Older ones are dead runs and don't count."""
    cutoff = now_utc().replace(tzinfo=None) - timedelta(seconds=SOFT_TIME_LIMIT * 2)
    return db.session.query(BackgroundTask.query.filter(
        BackgroundTask.user_id == user_id,
        BackgroundTask.task_type == TASK_TYPE,
        BackgroundTask.status.in_(('pending', 'running')),
        BackgroundTask.created_at >= cutoff,
    ).exists()).scalar()


def _start_row(user_id):
    row = BackgroundTask(id=str(uuid.uuid4()), user_id=user_id, task_type=TASK_TYPE,
                         status='running', started_at=now_utc())
    db.session.add(row)
    db.session.commit()
    return row.id


def _fail(user_id, row_ids, message):
    """Fail this run's row, or write a failed row when the run failed before finding work."""
    db.session.rollback()
    row = db.session.get(BackgroundTask, row_ids[0]) if row_ids else None
    if row is None:
        row = BackgroundTask(id=str(uuid.uuid4()), user_id=user_id, task_type=TASK_TYPE, started_at=now_utc())
        db.session.add(row)
    row.status = 'failed'
    row.completed_at = now_utc()
    row.error_message = message
    db.session.commit()
    return {'status': 'failed', 'message': message}
