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

# app/models/company.py

from app import db
from app.utils.time_utils import now_utc
from .associations import competitors_association


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)
    sector_id = db.Column(db.Integer, db.ForeignKey("sector.id"), nullable=True, index=True)
    industry = db.Column(db.String(150), nullable=True)
    intrinsic_value = db.Column(db.BigInteger, nullable=True)
    is_in_portfolio = db.Column(db.Boolean, default=False, nullable=False, index=True)
    reporting_currency = db.Column(db.String(3), nullable=True)  # Stock's native trading currency (e.g., USD, EUR)

    # Company Journey persistent wiki-style notes (BlockNote JSON)
    journey_notes = db.Column(db.Text, nullable=True)
    journey_notes_updated_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        # One company per ticker per user. Application-level guards existed on
        # every creation path but duplicates still got through.
        db.UniqueConstraint('user_id', 'ticker_symbol', name='uq_company_user_ticker'),
    )

    # Relationships
    sector = db.relationship("Sector", backref="companies")

    research_sessions = db.relationship(
        "ChecklistAnalysis",
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


class CompanyResource(db.Model):
    """Unified model for all company-related resources: files and links.
    Replaces CompanyDocument, CompanyArticle, and ResearchAttachment."""

    __tablename__ = "company_resource"

    id = db.Column(db.Integer, primary_key=True)

    # Core relationships
    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # 'file' or 'link'
    resource_type = db.Column(db.String(20), nullable=False, index=True)

    # Common fields
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True, index=True)

    # File-specific fields (null for links)
    original_filename = db.Column(db.String(255), nullable=True)
    stored_filename = db.Column(db.String(300), nullable=True, unique=True)
    file_type = db.Column(db.String(50), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    # Link-specific fields (null for files)
    url = db.Column(db.String(500), nullable=True)
    source_name = db.Column(db.String(100), nullable=True)

    # Optional research context
    research_project_id = db.Column(
        db.Integer,
        db.ForeignKey("research_project.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    research_step_index = db.Column(db.Integer, nullable=True)

    # Dates
    resource_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    # Relationships
    company = db.relationship(
        "Company",
        backref=db.backref("resources", lazy="dynamic", cascade="all, delete-orphan"),
    )
    research_project = db.relationship(
        "ResearchProject",
        backref=db.backref("resources", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<CompanyResource {self.resource_type}: {self.title}>"

    def to_dict(self):
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "resource_type": self.resource_type,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resource_date": self.resource_date.isoformat() if self.resource_date else None,
        }
        if self.resource_type == "file":
            data.update(
                {
                    "original_filename": self.original_filename,
                    "file_type": self.file_type,
                    "file_size": self.file_size,
                }
            )
        elif self.resource_type == "link":
            data.update(
                {
                    "url": self.url,
                    "source_name": self.source_name,
                }
            )
        if self.research_project_id:
            data["research_project_id"] = self.research_project_id
            data["research_step_index"] = self.research_step_index
        return data


class ScuttlebuttAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this analysis to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)

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
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)

    # Foreign key to link this analysis to the User who created it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

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
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)

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
