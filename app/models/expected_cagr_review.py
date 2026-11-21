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

from app import db


class ExpectedCagrReview(db.Model):
    """An expected return, saved before it became a CAGR, that may have been a total.

    The expected_cagr_rename migration fills this with the BUY decisions and thesis
    versions whose timeframe makes a total and a CAGR read differently. Each row is
    resolved once, by converting the original value, setting a new one, or keeping it.
    """
    __tablename__ = 'expected_cagr_review'
    __table_args__ = (db.UniqueConstraint('kind', 'entry_id', name='uq_expected_cagr_review_entry'),)

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)  # 'buy' (decision_journal) or 'thesis' (thesis_evolution)
    entry_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    original_value = db.Column(db.Float, nullable=False)  # As stored before the rename
    timeframe_months = db.Column(db.Integer, nullable=False)
    resolution = db.Column(db.String(10), nullable=True)  # None (open), 'converted', 'set' or 'kept'
    resolved_value = db.Column(db.Float, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
