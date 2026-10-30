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
Run history for the Celery beat jobs in celery_app.py `beat_schedule`.

Tasks don't call this directly: `record_job_run` in app/celery_tasks/base.py
wraps each scheduled task and writes one ScheduledJobRun row per run. The rest
backs the admin "Scheduled jobs" page (app/admin).
"""

from datetime import timedelta

from celery.schedules import crontab

from app import db
from app.models import ScheduledJobRun
from app.utils.time_utils import ensure_timezone_aware, now_utc
from celery_app import celery

RETENTION = timedelta(days=90)

# The reaper runs every 10 minutes, so it doubles as beat's heartbeat.
HEARTBEAT_JOB = 'ai-check-reap-stale-runs'
HEARTBEAT_MAX_AGE = timedelta(minutes=30)

# A worker killed mid-run (OOM, redeploy) never finishes its row. Past this age a
# `running` row is shown as interrupted; the row itself is left alone.
INTERRUPTED_AFTER = timedelta(hours=2)


def start_run(job_name, triggered_by='schedule', triggered_by_user_id=None):
    """Insert a `running` row and commit it, so a run that dies midway still shows. Returns its id."""
    run = ScheduledJobRun(
        job_name=job_name,
        started_at=now_utc(),
        status='running',
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )
    db.session.add(run)
    db.session.commit()
    return run.id


def finish_run(run_id, status, error=None):
    """Mark a run `success` or `failed` and commit."""
    run = db.session.get(ScheduledJobRun, run_id)
    run.status = status
    run.error = error
    run.finished_at = now_utc()
    db.session.commit()


def prune_job_runs(now=None):
    """Delete runs that started more than RETENTION ago. Returns how many."""
    cutoff = (now or now_utc()) - RETENTION
    deleted = ScheduledJobRun.query.filter(
        ScheduledJobRun.started_at < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return deleted


def scheduler_heartbeat_stale(now=None):
    """True when beat hasn't run HEARTBEAT_JOB within HEARTBEAT_MAX_AGE (or ever).

    Only scheduled runs count: a manual Run now proves the worker is up, not beat.
    """
    cutoff = (now or now_utc()) - HEARTBEAT_MAX_AGE
    recent = ScheduledJobRun.query.filter(
        ScheduledJobRun.job_name == HEARTBEAT_JOB,
        ScheduledJobRun.triggered_by == 'schedule',
        ScheduledJobRun.started_at >= cutoff,
    ).first()
    return recent is None


def job_statuses(now=None):
    """One dict per beat_schedule entry, in schedule order, for the admin page."""
    now = now or now_utc()
    statuses = []
    for name, entry in celery.conf.beat_schedule.items():
        schedule = entry['schedule']
        latest = ScheduledJobRun.query.filter_by(job_name=name).order_by(ScheduledJobRun.started_at.desc())
        last_run = latest.first()
        statuses.append({
            'name': name,
            'task': entry['task'],
            'schedule': _schedule_text(schedule),
            # remaining_estimate lands a hair before the minute; round to the second.
            'next_run': (now + schedule.remaining_estimate(now) + timedelta(milliseconds=500)).replace(microsecond=0),
            'last_run': last_run,
            'last_status': _display_status(last_run, now),
            'last_failure': latest.filter(ScheduledJobRun.status == 'failed').first(),
        })
    return statuses


def enqueue_job(job_name, user_id):
    """Queue a beat job now, recorded as a manual run by `user_id`. KeyError for a job not in beat_schedule."""
    entry = celery.conf.beat_schedule[job_name]
    celery.send_task(entry['task'], kwargs={'triggered_by': 'manual', 'triggered_by_user_id': user_id})


def _display_status(run, now):
    if run is None:
        return None
    if run.status == 'running' and now - ensure_timezone_aware(run.started_at) > INTERRUPTED_AFTER:
        return 'interrupted'
    return run.status


def _schedule_text(schedule):
    if isinstance(schedule, crontab):
        return ' '.join(str(part) for part in (
            schedule._orig_minute, schedule._orig_hour, schedule._orig_day_of_month,
            schedule._orig_month_of_year, schedule._orig_day_of_week))
    return str(schedule)
