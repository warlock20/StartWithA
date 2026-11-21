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

# app/models/user_monitor_setting.py

from app import db
from app.utils.time_utils import now_utc


class UserMonitorSetting(db.Model):
    """A user's override of one background monitor's schedule (#436).

    NULL enabled/frequency mean "use the registry default". No relationship on User:
    the database cascades deletes (ondelete='CASCADE').
    """
    __tablename__ = 'user_monitor_setting'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    monitor_key = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, nullable=True)
    frequency = db.Column(db.String(10), nullable=True)  # off, daily, weekly, monthly
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'monitor_key', name='uq_user_monitor_setting_user_monitor'),
        db.CheckConstraint(
            "frequency IS NULL OR frequency IN ('off','daily','weekly','monthly')",
            name='ck_user_monitor_setting_frequency'),
    )

    def __repr__(self):
        return f'<UserMonitorSetting user={self.user_id} {self.monitor_key}>'
