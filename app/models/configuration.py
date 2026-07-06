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
Configuration Models

System-wide configuration and user investment profiles for
tunable thresholds throughout the platform.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from app import db

class SystemConfig(db.Model):
    """
    System-wide configuration defaults.
    
    Stores all tunable parameters with their default values.
    These can be overridden by investor profiles or individual users.
    """
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Configuration key (unique identifier)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Value stored as JSON for flexibility (can be int, float, string, dict, list)
    value = db.Column(db.JSON, nullable=False)
    
    # Metadata
    description = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)  # 'research', 'portfolio', 'alerts', etc.
    data_type = db.Column(db.String(20), default='number')  # 'number', 'percent', 'boolean', 'string'
    
    # Constraints for validation
    min_value = db.Column(db.Float, nullable=True)
    max_value = db.Column(db.Float, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemConfig {self.key}={self.value}>'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'category': self.category,
            'data_type': self.data_type,
            'min_value': self.min_value,
            'max_value': self.max_value
        }


class InvestorProfile(db.Model):
    """
    Predefined investor profiles with preset thresholds.
    
    Profiles: beginner, intermediate, expert, professional
    Each profile has different threshold values appropriate for that level.
    """
    __tablename__ = 'investor_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Profile identifier
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'beginner', 'intermediate', etc.
    display_name = db.Column(db.String(100), nullable=False)  # 'Beginner Investor'
    description = db.Column(db.Text)
    
    # All overrides for this profile stored as JSON
    # Format: {"config_key": value, "config_key2": value2, ...}
    config_overrides = db.Column(db.JSON, nullable=False, default=dict)
    
    # UI settings
    icon = db.Column(db.String(50), default='user')  # FontAwesome icon name
    color = db.Column(db.String(20), default='primary')  # Bootstrap color class
    sort_order = db.Column(db.Integer, default=0)
    
    # Is this profile active/available for selection?
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InvestorProfile {self.name}>'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'config_overrides': self.config_overrides,
            'icon': self.icon,
            'color': self.color,
            'is_active': self.is_active
        }
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific config value from this profile's overrides."""
        return self.config_overrides.get(key, default)


class UserInvestmentProfile(db.Model):
    """
    Links a user to their chosen investor profile with optional custom overrides.
    
    Users can:
    1. Select a base profile (beginner, intermediate, expert, professional)
    2. Optionally override specific settings for personalization
    """
    __tablename__ = 'user_investment_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to user (one-to-one relationship)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    
    # Selected base profile
    profile_id = db.Column(db.Integer, db.ForeignKey('investor_profile.id'), nullable=True)
    
    # Custom overrides on top of the profile
    # Format: {"config_key": value, ...}
    custom_overrides = db.Column(db.JSON, default=dict)
    
    # User's investment experience (for recommendations)
    years_experience = db.Column(db.Integer, nullable=True)
    investment_style = db.Column(db.String(50), nullable=True)  # 'value', 'growth', 'dividend', 'mixed'
    risk_tolerance = db.Column(db.String(20), nullable=True)  # 'conservative', 'moderate', 'aggressive'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('investment_profile', uselist=False))
    profile = db.relationship('InvestorProfile', backref='users')
    
    def __repr__(self):
        return f'<UserInvestmentProfile user_id={self.user_id}>'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'profile_id': self.profile_id,
            'profile_name': self.profile.name if self.profile else None,
            'custom_overrides': self.custom_overrides,
            'years_experience': self.years_experience,
            'investment_style': self.investment_style,
            'risk_tolerance': self.risk_tolerance
        }
    
    def get_effective_config(self, key: str, system_default: Any = None) -> Any:
        """
        Get the effective config value for this user.
        
        Priority: custom_overrides > profile_overrides > system_default
        """
        # Check custom overrides first
        if self.custom_overrides and key in self.custom_overrides:
            return self.custom_overrides[key]
        
        # Check profile overrides
        if self.profile and self.profile.config_overrides:
            if key in self.profile.config_overrides:
                return self.profile.config_overrides[key]
        
        # Fall back to system default
        return system_default
    
    def set_custom_override(self, key: str, value: Any) -> None:
        """Set a custom override for a specific config key."""
        if self.custom_overrides is None:
            self.custom_overrides = {}
        self.custom_overrides[key] = value
    
    def remove_custom_override(self, key: str) -> None:
        """Remove a custom override, reverting to profile/system default."""
        if self.custom_overrides and key in self.custom_overrides:
            del self.custom_overrides[key]


# ============================================
# Configuration Categories & Keys Reference
# ============================================
"""
CATEGORY: research_quality
- min_time_minutes: Minimum research time for "good" score
- min_questions_pct: Minimum % of questions to answer
- good_answer_length: Character count for quality answers
- ideal_documents: Number of documents for thorough research

CATEGORY: outcome_tracking
- big_win_threshold: % return to count as "big win"
- big_loss_threshold: % loss to count as "big loss"
- min_outcomes_for_analysis: Minimum trades to show correlation

CATEGORY: portfolio_alerts
- concentration_warning_pct: Single position % to trigger warning
- sector_concentration_pct: Sector % to trigger warning
- correlation_threshold: Correlation coefficient for warning
- min_research_score: Minimum score before warning

CATEGORY: behavioral_patterns
- min_hold_days_for_pattern: Days to include in hold time analysis
- overconfidence_threshold: Confidence level to flag
- selling_winners_threshold: % gain at which selling is "too early"
- holding_losers_threshold: % loss to flag as "holding too long"

CATEGORY: thesis_analysis
- min_thesis_length: Characters for valid thesis
- quality_score_threshold: Score below which to warn
- max_assumptions: Number of key assumptions to identify
"""