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
Portfolio UI Insights Model

Stores historical AI-generated portfolio analysis for trend tracking.
Each analysis run creates a new record, enabling comparison over time.
"""

from app import db
from app.utils.time_utils import now_utc


class PortfolioUIInsight(db.Model):
    """
    Stores portfolio AI analysis results for historical tracking.

    Unlike BackgroundTask which is ephemeral, this table retains
    all analyses to enable trend tracking over time.
    """
    __tablename__ = 'portfolio_ui_insights'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Analysis metadata
    template_name = db.Column(db.String(100), nullable=False, default='portfolio_raw_trade_analysis')
    generated_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    # Full analysis results (JSON)
    insights_json = db.Column(db.JSON, nullable=False)

    # Token usage for cost tracking
    tokens_used = db.Column(db.Integer, default=0)

    # Portfolio state at time of analysis (for context)
    portfolio_value = db.Column(db.Numeric(18, 2), nullable=True)
    position_count = db.Column(db.Integer, nullable=True)
    last_transaction_date = db.Column(db.Date, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('portfolio_insights', lazy='dynamic'))

    def __repr__(self):
        return f'<PortfolioUIInsight user={self.user_id} generated_at={self.generated_at}>'

    @classmethod
    def save_analysis(cls, user_id, template_name, insights, tokens_used=0,
                      portfolio_value=None, position_count=None, last_transaction_date=None):
        """
        Create and save a new portfolio insight record.

        Args:
            user_id: User ID
            template_name: Analysis template used
            insights: Dict containing the full analysis results
            tokens_used: Number of AI tokens consumed
            portfolio_value: Total portfolio value at time of analysis
            position_count: Number of active positions
            last_transaction_date: Date of most recent transaction

        Returns:
            The created PortfolioUIInsight instance
        """
        insight = cls(
            user_id=user_id,
            template_name=template_name,
            insights_json=insights,
            tokens_used=tokens_used,
            portfolio_value=portfolio_value,
            position_count=position_count,
            last_transaction_date=last_transaction_date
        )
        db.session.add(insight)
        db.session.commit()
        return insight

    @classmethod
    def get_latest(cls, user_id, template_name=None):
        """
        Get the most recent analysis for a user.

        Args:
            user_id: User ID
            template_name: Optional filter by template

        Returns:
            PortfolioUIInsight or None
        """
        query = cls.query.filter_by(user_id=user_id)
        if template_name:
            query = query.filter_by(template_name=template_name)
        return query.order_by(cls.generated_at.desc()).first()

    @classmethod
    def get_history(cls, user_id, template_name=None, limit=10):
        """
        Get historical analyses for a user.

        Args:
            user_id: User ID
            template_name: Optional filter by template
            limit: Maximum number of records to return

        Returns:
            List of PortfolioUIInsight records, newest first
        """
        query = cls.query.filter_by(user_id=user_id)
        if template_name:
            query = query.filter_by(template_name=template_name)
        return query.order_by(cls.generated_at.desc()).limit(limit).all()

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'template_name': self.template_name,
            'insights': self.insights_json,
            'tokens_used': self.tokens_used,
            'portfolio_value': float(self.portfolio_value) if self.portfolio_value else None,
            'position_count': self.position_count,
            'last_transaction_date': self.last_transaction_date.isoformat() if self.last_transaction_date else None
        }

    def to_summary_dict(self):
        """Convert to summary dictionary (without full insights)."""
        return {
            'id': self.id,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'template_name': self.template_name,
            'tokens_used': self.tokens_used,
            'portfolio_value': float(self.portfolio_value) if self.portfolio_value else None,
            'position_count': self.position_count
        }
