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
from app.utils.time_utils import now_utc


class MarketSweep(db.Model):
    """Admin-uploaded list of companies for a country/market."""
    __tablename__ = 'market_sweep'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    total_companies = db.Column(db.Integer, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc)
    is_active = db.Column(db.Boolean, default=True)

    companies = db.relationship('MarketSweepCompany', backref='sweep', lazy='dynamic',
                                cascade='all, delete-orphan',
                                order_by='MarketSweepCompany.sort_order')
    uploader = db.relationship('User')

    def __repr__(self):
        return f'<MarketSweep {self.name}>'


class MarketSweepCompany(db.Model):
    """Individual company from an admin-uploaded market sweep."""
    __tablename__ = 'market_sweep_company'

    id = db.Column(db.Integer, primary_key=True)
    sweep_id = db.Column(db.Integer, db.ForeignKey('market_sweep.id'), nullable=False, index=True)
    company_name = db.Column(db.String(300), nullable=False)
    ticker = db.Column(db.String(50))
    sector_label = db.Column(db.String(200))
    market_cap = db.Column(db.String(50))
    exchange = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, default=0, index=True)

    # ISIN of this listing. Nullable permanently -- most rows will never have
    # one, and a guessed value is worse than a missing one.
    isin = db.Column(db.String(12), nullable=True, index=True)

    decisions = db.relationship('MarketSweepDecision', backref='sweep_company', lazy='dynamic',
                                cascade='all, delete-orphan')

    def __repr__(self):
        return f'<MarketSweepCompany {self.company_name}>'


class MarketSweepDecision(db.Model):
    """User's decision on a market sweep company."""
    __tablename__ = 'market_sweep_decision'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'sweep_company_id', name='_user_sweep_company_uc'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    sweep_company_id = db.Column(db.Integer, db.ForeignKey('market_sweep_company.id'), nullable=False, index=True)
    decision = db.Column(db.String(20), nullable=False)  # 'skip', 'inbox', 'killed'
    notes = db.Column(db.Text)
    kill_reasons = db.Column(db.JSON)
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True)
    promoted_idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id'), nullable=True)
    decided_at = db.Column(db.DateTime, default=now_utc)

    user = db.relationship('User')
    sector = db.relationship('Sector')
    promoted_idea = db.relationship('IdeaPipeline')

    def __repr__(self):
        return f'<MarketSweepDecision {self.decision}>'


class CompanySweepLink(db.Model):
    """Which of this user's companies a sweep row is.

    A sweep row is global; a company belongs to one user. The answer therefore
    differs per user and cannot live on the row.

    Stored, never re-derived. Identity is a judgement about the world, not a
    computation over the user's own records: re-running it can change the answer
    when a row is renamed or a matching rule is tuned, so it is remembered
    instead. (State, which is a computation, is derived on read and never
    stored -- see app/services/company_state.py.)
    """
    __tablename__ = 'company_sweep_link'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'sweep_company_id',
                            name='_user_sweep_company_link_uc'),
    )

    #: The user decided on the row; the link follows from that decision.
    ORIGIN_DECISION = 'decision'
    #: Both sides carry the same ISIN. Exact, no judgement involved.
    ORIGIN_ISIN = 'isin'
    #: A human accepted a suggestion. Equal in standing to the other two.
    ORIGIN_CONFIRMED = 'confirmed'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    sweep_company_id = db.Column(
        db.Integer, db.ForeignKey('market_sweep_company.id', ondelete='CASCADE'),
        nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    origin = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    def __repr__(self):
        return f'<CompanySweepLink {self.sweep_company_id}->{self.company_id}>'
