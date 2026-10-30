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

# app/models/scheduled_job_run.py

from app import db
from app.utils.time_utils import now_utc


class ScheduledJobRun(db.Model):
    """One run of a Celery beat job. Celery keeps no run history, so this is it."""
    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(100), nullable=False)  # the beat_schedule key
    started_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default='running')  # running, success, failed
    error = db.Column(db.Text)

    triggered_by = db.Column(db.String(20), nullable=False, default='schedule')  # schedule, manual
    triggered_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))

    __table_args__ = (
        db.Index('ix_scheduled_job_run_job_started', 'job_name', 'started_at'),
    )

    @property
    def duration(self):
        """timedelta from start to finish, or None while running."""
        if self.finished_at is None:
            return None
        return self.finished_at - self.started_at

    def __repr__(self):
        return f'<ScheduledJobRun {self.id} {self.job_name} {self.status}>'
