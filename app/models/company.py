# app/models/company.py

from app import db
from app.utils.time_utils import now_utc
from .associations import competitors_association


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    sector_id = db.Column(db.Integer, db.ForeignKey("sector.id"), nullable=True, index=True)
    industry = db.Column(db.String(150), nullable=True)
    intrinsic_value = db.Column(db.BigInteger, nullable=True)
    is_in_portfolio = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Relationships
    sector = db.relationship("Sector", backref="companies")

    research_sessions = db.relationship(
        "ResearchSession",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    documents = db.relationship(
        "CompanyDocument",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    articles = db.relationship(
        "CompanyArticle",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    destination_checkpoints = db.relationship(
        "DestinationCheckpoint",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    scuttlebutt_analyses = db.relationship(
        "ScuttlebuttAnalysis",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    qualitative_analyses = db.relationship(
        "QualitativeAnalysis",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    financial_data = db.relationship(
        "FinancialData", backref="company", lazy="dynamic", cascade="all, delete-orphan"
    )

    competitors = db.relationship(
        "Company",  # The relationship is with the Company model itself
        secondary=competitors_association,  # Use our association table to link them
        primaryjoin=(competitors_association.c.company_id == id),
        secondaryjoin=(competitors_association.c.competitor_id == id),
        backref=db.backref(
            "competed_by", lazy="dynamic"
        ),  # Allows finding who competes WITH this company
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Company {self.ticker_symbol} - {self.name}>"


class CompanyDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this document to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this document to the User who uploaded it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    original_filename = db.Column(
        db.String(255), nullable=False
    )  # Original name of the uploaded file
    # Stored file path, relative to a base upload directory.
    # Could be a unique generated filename or include subdirectories like company_id/
    stored_filename = db.Column(db.String(300), nullable=False, unique=True)

    document_group = db.Column(
        db.String(100), nullable=False, index=True
    )  # E.g., 'Annual Reports', 'Quarterly Reports', 'Analyst Transcripts'
    document_title = db.Column(
        db.String(255), nullable=True
    )  # E.g., "2023 Annual Report", "Q4 2023 Earnings Call"
    document_date = db.Column(
        db.Date, nullable=True
    )  # Publication date of the document, or period end date

    description = db.Column(db.Text, nullable=True)  # Optional user description
    uploaded_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    # Relationships (these will create the backrefs on Company and User)
    # company = db.relationship('Company', backref=db.backref('documents', lazy='dynamic')) # This is one way
    # uploader = db.relationship('User', backref=db.backref('uploaded_documents', lazy='dynamic')) # This is one way

    def __repr__(self):
        return (
            f"<CompanyDocument {self.original_filename} for Company {self.company_id}>"
        )


class CompanyArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this article to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # The title of the article
    title = db.Column(db.String(300), nullable=False)

    # The URL to the original article - should be unique to avoid duplicates
    url = db.Column(db.String(500), nullable=False, unique=True)

    # A short description or snippet of the article
    description = db.Column(db.Text, nullable=True)

    # The name of the news source (e.g., "Reuters", "Bloomberg")
    source_name = db.Column(db.String(100), nullable=True)

    # The original publication date of the article
    published_at = db.Column(db.DateTime, nullable=False, index=True)

    # The date we fetched the article
    fetched_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def __repr__(self):
        return f"<CompanyArticle {self.title[:50]}...>"


class ScuttlebuttAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this analysis to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # The full summary text generated by the AI
    generated_summary = db.Column(db.Text, nullable=False)

    # The date the analysis was generated
    generated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, index=True
    )

    def __repr__(self):
        return f"<ScuttlebuttAnalysis for Company {self.company_id} on {self.generated_at}>"


class QualitativeAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this analysis to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this analysis to the User who created it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # This field will store which model is being used, e.g., 'SWOT'
    model_type = db.Column(db.String(50), nullable=False, index=True)

    # We'll use a JSON field to store the structured data.
    # For SWOT, it will look like: {"strengths": "...", "weaknesses": "...", ...}
    content = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )

    # Ensure a user can only have one of each analysis type per company
    __table_args__ = (
        db.UniqueConstraint(
            "company_id", "user_id", "model_type", name="uq_user_company_analysis"
        ),
    )

    def __repr__(self):
        return f"<QualitativeAnalysis {self.model_type} for Company {self.company_id}>"


class FinancialData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # e.g., 'income_statement', 'balance_sheet', 'cash_flow'
    statement_type = db.Column(db.String(50), nullable=False, index=True)

    # The name of the line item, e.g., 'Total Revenue', 'Net Income'
    metric_name = db.Column(db.String(100), nullable=False, index=True)

    # The end date of the financial period (e.g., year or quarter end)
    period_date = db.Column(db.Date, nullable=False, index=True)

    # The actual value of the metric
    value = db.Column(db.BigInteger, nullable=False)

    # Ensure we only have one value for each metric on a specific date for a company
    __table_args__ = (
        db.UniqueConstraint(
            "company_id", "metric_name", "period_date", name="uq_company_metric_period"
        ),
    )

    def __repr__(self):
        return f"<FinancialData {self.metric_name} for Company {self.company_id} on {self.period_date}>"
