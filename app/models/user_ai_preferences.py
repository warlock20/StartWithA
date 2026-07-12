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
User AI Preferences Model

Stores per-user model/provider overrides for each prompt category.
Enables users to select which AI model to use for different task types
without requiring server restarts or environment variable changes.

Priority chain (highest to lowest):
    1. User override (this table)
    2. YAML prompt config (model field in prompt YAML)
    3. AITaskType routing (QUALITY_TASKS / FAST_TASKS)
    4. Environment variable defaults
"""

from app import db
from app.utils.time_utils import now_utc


class UserAIPreference(db.Model):
    """
    Per-user AI model override for a prompt category.

    Each row represents a user's chosen model for a specific prompt
    category (e.g., 'screening', 'research', 'companion').
    """
    __tablename__ = 'user_ai_preference'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False, index=True
    )
    # Prompt category matches directory names under app/services/ai/prompts/
    # e.g. 'screening', 'research', 'companion', 'checkpoint', 'intelligence'
    prompt_category = db.Column(db.String(50), nullable=False)

    # Model override — string matching AIModel.from_string() keys
    # e.g. 'gemini-2.5-flash', 'claude-sonnet-4', 'deepseek-v3'
    model_override = db.Column(db.String(100), nullable=True)

    # Provider override — string matching AIProvider enum values
    # e.g. 'gemini', 'claude', 'deepseek'
    provider_override = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'prompt_category', name='uq_user_prompt_category'),
    )

    # Relationship
    user = db.relationship('User', backref=db.backref('ai_preferences', lazy='dynamic'))

    def __repr__(self):
        return (
            f'<UserAIPreference user={self.user_id} '
            f'category={self.prompt_category} '
            f'model={self.model_override}>'
        )

    def to_dict(self):
        return {
            'id': self.id,
            'prompt_category': self.prompt_category,
            'model_override': self.model_override,
            'provider_override': self.provider_override,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_user_preferences(cls, user_id):
        """Get all AI preferences for a user as a dict keyed by category."""
        prefs = cls.query.filter_by(user_id=user_id).all()
        return {p.prompt_category: p for p in prefs}

    @classmethod
    def get_preference(cls, user_id, prompt_category):
        """Get a single preference for a user and category."""
        return cls.query.filter_by(
            user_id=user_id, prompt_category=prompt_category
        ).first()

    @classmethod
    def set_preference(cls, user_id, prompt_category, model_override=None, provider_override=None):
        """Set or update a user's model preference for a prompt category."""
        pref = cls.query.filter_by(
            user_id=user_id, prompt_category=prompt_category
        ).first()

        if pref:
            pref.model_override = model_override
            pref.provider_override = provider_override
            pref.updated_at = now_utc()
        else:
            pref = cls(
                user_id=user_id,
                prompt_category=prompt_category,
                model_override=model_override,
                provider_override=provider_override,
            )
            db.session.add(pref)

        db.session.flush()
        return pref

    @classmethod
    def clear_preference(cls, user_id, prompt_category):
        """Remove a user's override for a prompt category (reset to default)."""
        pref = cls.query.filter_by(
            user_id=user_id, prompt_category=prompt_category
        ).first()
        if pref:
            db.session.delete(pref)
            db.session.flush()
            return True
        return False
