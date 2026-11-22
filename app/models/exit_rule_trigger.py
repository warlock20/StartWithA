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

# app/models/exit_rule_trigger.py

from sqlalchemy import text

from app import db
from app.utils.time_utils import now_utc


class ExitRuleTrigger(db.Model):
    """One episode of a must-exit rule going from intact to at_risk or triggered (#437).

    AIInsight rows are the check history; the episode holds the user's response
    (sold, held, ignored). A non-null sold_pct means the position was trimmed
    or exited; it is kept when a later hold sets response to 'held'. Datetimes are naive UTC. No relationships: the database
    cascades deletes (ondelete='CASCADE').
    """
    __tablename__ = 'exit_rule_trigger'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id', ondelete='CASCADE'), nullable=False)
    opened_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    opening_insight_id = db.Column(db.Integer, db.ForeignKey('ai_insight.id', ondelete='SET NULL'), nullable=True)
    worst_status = db.Column(db.String(10), nullable=False)
    current_status = db.Column(db.String(10), nullable=False)
    price_at_open = db.Column(db.Numeric(14, 4), nullable=True)
    price_currency = db.Column(db.String(3), nullable=True)
    response = db.Column(db.String(10), nullable=False, default='pending')  # pending, sold, held, ignored
    responded_at = db.Column(db.DateTime, nullable=True)
    hold_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id', ondelete='SET NULL'), nullable=True)
    held_at = db.Column(db.DateTime, nullable=True)
    ignored_at = db.Column(db.DateTime, nullable=True)
    sold_pct = db.Column(db.Float, nullable=True)
    sold_after_hold = db.Column(db.Boolean, nullable=False, default=False)
    realerted_at = db.Column(db.DateTime, nullable=True)
    realert_reason = db.Column(db.String(12), nullable=True)  # worse, new_source, reask
    closed_at = db.Column(db.DateTime, nullable=True)
    close_reason = db.Column(db.String(20), nullable=True)  # intact, rule_archived, position_closed
    created_at = db.Column(db.DateTime, default=now_utc)

    __table_args__ = (
        db.Index('ix_exit_rule_trigger_user_closed', 'user_id', 'closed_at'),
        db.Index('ix_exit_rule_trigger_rule_closed', 'rule_id', 'closed_at'),
        db.Index('uq_exit_rule_trigger_open_rule', 'rule_id', unique=True,
                 postgresql_where=text('closed_at IS NULL')),
    )

    def __repr__(self):
        return f'<ExitRuleTrigger rule={self.rule_id} {self.current_status} {self.response}>'
