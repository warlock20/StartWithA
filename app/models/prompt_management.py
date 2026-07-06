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
Prompt Management Models

Models for managing AI prompts, versions, and usage analytics.
"""

from datetime import datetime
from app import db


class PromptVersion(db.Model):
    """
    Track versions of AI prompts for A/B testing and rollback.
    """
    __tablename__ = 'prompt_version'

    id = db.Column(db.Integer, primary_key=True)

    # Prompt identification
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    version = db.Column(db.String(20), nullable=False)  # e.g., "1.0", "1.1", "2.0-beta"

    # Version details
    template = db.Column(db.Text, nullable=False)
    system_context = db.Column(db.Text)

    # AI configuration
    preferred_provider = db.Column(db.String(20))  # "claude", "gemini", "openai"
    model = db.Column(db.String(50))
    max_tokens = db.Column(db.Integer)
    temperature = db.Column(db.Float)

    # Status
    is_active = db.Column(db.Boolean, default=False, index=True)
    is_default = db.Column(db.Boolean, default=False)

    # Metadata
    description = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    notes = db.Column(db.Text)  # A/B test notes, tuning observations

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    activated_at = db.Column(db.DateTime)

    # Relationships
    usage_logs = db.relationship('PromptUsageLog', back_populates='prompt_version',
                                 lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PromptVersion {self.name} v{self.version}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'version': self.version,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'preferred_provider': self.preferred_provider,
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
        }


class PromptUsageLog(db.Model):
    """
    Analytics: Track every prompt execution for cost and performance analysis.
    """
    __tablename__ = 'prompt_usage_log'

    id = db.Column(db.Integer, primary_key=True)

    # Prompt details
    prompt_version_id = db.Column(db.Integer, db.ForeignKey('prompt_version.id'), index=True)
    prompt_name = db.Column(db.String(100), nullable=False, index=True)
    prompt_version = db.Column(db.String(20))

    # Execution details
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    provider = db.Column(db.String(20))  # "claude", "gemini", etc.
    model = db.Column(db.String(50))

    # Token usage
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)

    # Cost (in cents)
    estimated_cost_cents = db.Column(db.Integer)

    # Performance
    latency_ms = db.Column(db.Integer)  # Response time in milliseconds
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)

    # Context
    context_data = db.Column(db.JSON)  # Store parameters passed to prompt

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    prompt_version = db.relationship('PromptVersion', back_populates='usage_logs')
    user = db.relationship('User', backref=db.backref('prompt_usage', lazy='dynamic'))

    def __repr__(self):
        return f'<PromptUsageLog {self.prompt_name} v{self.prompt_version}>'

    @property
    def estimated_cost_dollars(self):
        """Get cost in dollars"""
        return self.estimated_cost_cents / 100.0 if self.estimated_cost_cents else 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'prompt_name': self.prompt_name,
            'prompt_version': self.prompt_version,
            'provider': self.provider,
            'model': self.model,
            'total_tokens': self.total_tokens,
            'estimated_cost_dollars': self.estimated_cost_dollars,
            'latency_ms': self.latency_ms,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
