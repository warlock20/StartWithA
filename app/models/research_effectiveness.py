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

# app/models/research_effectiveness.py

from app import db
from app.utils.time_utils import now_utc


class ResearchEffectivenessDismissal(db.Model):
    """A research-effectiveness finding the user dismissed (#440).

    `counts` snapshots the evidence at dismissal time as
    {'closed': [[label, trades, wins], ...], 'all': [...]}, so the finding can
    come back once the numbers move. Datetimes are naive UTC.
    """
    __tablename__ = 'research_effectiveness_dismissal'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'finding_key', name='uq_research_effectiveness_dismissal_user_key'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    finding_key = db.Column(db.String(120), nullable=False)
    counts = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
