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
