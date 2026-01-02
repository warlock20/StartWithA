"""
Configuration Service

Centralized service for retrieving effective configuration values.
Handles the priority chain: user overrides > profile > system defaults

Usage:
    from app.services.config_service import ConfigService, get_config
    
    # Get single value
    threshold = get_config('concentration_warning_pct', user_id=current_user.id)
    
    # Get all config for a user
    config = ConfigService.get_user_config(user_id)
    threshold = config['concentration_warning_pct']
    
    # Get category of configs
    alerts = ConfigService.get_category('portfolio_alerts', user_id)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.utils.time_utils import now_utc
from app import db
from app.models.configuration import (
    SystemConfig,
    InvestorProfile,
    UserInvestmentProfile
)
from sqlalchemy.orm.attributes import flag_modified
logger = logging.getLogger(__name__)


class ConfigService:
    """
    Service for managing and retrieving configuration values.
    
    Priority chain:
    1. User's custom overrides (highest priority)
    2. User's selected investor profile
    3. System defaults (lowest priority)
    """
    
    # Cache for system defaults (refreshed periodically)
    _system_cache: Dict[str, Any] = {}
    _cache_timestamp: Optional[datetime] = None
    _cache_ttl_seconds = 300  # 5 minutes
    
    # ============================================
    # PUBLIC API
    # ============================================
    
    @classmethod
    def get(
        cls,
        key: str,
        user_id: Optional[int] = None,
        default: Any = None
    ) -> Any:
        """
        Get a configuration value with full priority chain.
        
        Args:
            key: Configuration key (e.g., 'concentration_warning_pct')
            user_id: Optional user ID for personalized config
            default: Fallback if key not found anywhere
            
        Returns:
            Effective configuration value
        """
        # Get system default first
        system_value = cls._get_system_default(key)
        
        if user_id is None:
            return system_value if system_value is not None else default
        
        # Get user's investment profile
        user_profile = cls._get_user_profile(user_id)
        
        if user_profile is None:
            return system_value if system_value is not None else default
        
        # Check user's custom overrides first
        if user_profile.custom_overrides and key in user_profile.custom_overrides:
            return user_profile.custom_overrides[key]
        
        # Check profile overrides
        if user_profile.profile and user_profile.profile.config_overrides:
            if key in user_profile.profile.config_overrides:
                return user_profile.profile.config_overrides[key]
        
        # Fall back to system default
        return system_value if system_value is not None else default
    
    @classmethod
    def get_user_config(cls, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all effective configuration values for a user.
        
        Args:
            user_id: Optional user ID
            
        Returns:
            Dict of all config keys with their effective values
        """
        # Start with system defaults
        config = cls._get_all_system_defaults()
        
        if user_id is None:
            return config
        
        # Get user profile
        user_profile = cls._get_user_profile(user_id)
        
        if user_profile is None:
            return config
        
        # Apply profile overrides
        if user_profile.profile and user_profile.profile.config_overrides:
            config.update(user_profile.profile.config_overrides)
        
        # Apply user's custom overrides (highest priority)
        if user_profile.custom_overrides:
            config.update(user_profile.custom_overrides)
        
        return config
    
    @classmethod
    def get_category(
        cls,
        category: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get all config values for a specific category.
        
        Args:
            category: Category name (e.g., 'portfolio_alerts')
            user_id: Optional user ID
            
        Returns:
            Dict of config keys in that category with effective values
        """
        # Get all configs for user
        all_config = cls.get_user_config(user_id)
        
        # Filter by category
        category_keys = cls._get_category_keys(category)
        
        return {k: all_config.get(k) for k in category_keys if k in all_config}
    
    @classmethod
    def get_with_metadata(
        cls,
        key: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get config value with metadata (description, constraints, source).
        
        Useful for displaying in settings UI.
        """
        system_config = SystemConfig.query.filter_by(key=key).first()
        
        if not system_config:
            return {'key': key, 'value': None, 'error': 'Key not found'}
        
        effective_value = cls.get(key, user_id)
        source = cls._determine_source(key, user_id)
        
        return {
            'key': key,
            'value': effective_value,
            'system_default': system_config.value,
            'description': system_config.description,
            'category': system_config.category,
            'data_type': system_config.data_type,
            'min_value': system_config.min_value,
            'max_value': system_config.max_value,
            'source': source  # 'system', 'profile', or 'custom'
        }
    
    # ============================================
    # USER PROFILE MANAGEMENT
    # ============================================
    
    @classmethod
    def set_user_profile(
        cls,
        user_id: int,
        profile_name: str
    ) -> UserInvestmentProfile:
        """
        Set a user's investor profile.
        
        Args:
            user_id: User ID
            profile_name: Profile name ('beginner', 'intermediate', etc.)
            
        Returns:
            Updated UserInvestmentProfile
        """
        profile = InvestorProfile.query.filter_by(name=profile_name, is_active=True).first()
        
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found or inactive")
        
        user_profile = UserInvestmentProfile.query.filter_by(user_id=user_id).first()
        
        if user_profile:
            user_profile.profile_id = profile.id
            user_profile.updated_at = now_utc()
        else:
            user_profile = UserInvestmentProfile(
                user_id=user_id,
                profile_id=profile.id
            )
            db.session.add(user_profile)
        
        db.session.commit()
        logger.info(f"Set user {user_id} profile to '{profile_name}'")
        
        return user_profile
    
    @classmethod
    def set_custom_override(
        cls,
        user_id: int,
        key: str,
        value: Any
    ) -> UserInvestmentProfile:
        """
        Set a custom override for a specific config key.
        
        Args:
            user_id: User ID
            key: Config key
            value: Override value
            
        Returns:
            Updated UserInvestmentProfile
        """
        # Validate the key exists
        system_config = SystemConfig.query.filter_by(key=key).first()
        if not system_config:
            raise ValueError(f"Config key '{key}' not found")
        
        # Validate value constraints
        if system_config.min_value is not None and value < system_config.min_value:
            raise ValueError(f"Value must be >= {system_config.min_value}")
        if system_config.max_value is not None and value > system_config.max_value:
            raise ValueError(f"Value must be <= {system_config.max_value}")
        
        # Get or create user profile
        user_profile = UserInvestmentProfile.query.filter_by(user_id=user_id).first()
        
        if not user_profile:
            user_profile = UserInvestmentProfile(
                user_id=user_id,
                custom_overrides={}
            )
            db.session.add(user_profile)
        
        if user_profile.custom_overrides is None:
            user_profile.custom_overrides = {}
        
        user_profile.custom_overrides[key] = value
        user_profile.updated_at = now_utc()
        
        # Mark as modified for SQLAlchemy to detect JSON change
        flag_modified(user_profile, 'custom_overrides')
        
        db.session.commit()
        logger.info(f"Set custom override for user {user_id}: {key}={value}")
        
        return user_profile
    
    @classmethod
    def remove_custom_override(
        cls,
        user_id: int,
        key: str
    ) -> UserInvestmentProfile:
        """
        Remove a custom override, reverting to profile/system default.
        """
        user_profile = UserInvestmentProfile.query.filter_by(user_id=user_id).first()
        
        if user_profile and user_profile.custom_overrides and key in user_profile.custom_overrides:
            del user_profile.custom_overrides[key]
            user_profile.updated_at = now_utc()
            
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(user_profile, 'custom_overrides')
            
            db.session.commit()
            logger.info(f"Removed custom override for user {user_id}: {key}")
        
        return user_profile
    
    @classmethod
    def reset_to_profile_defaults(cls, user_id: int) -> UserInvestmentProfile:
        """
        Clear all custom overrides for a user.
        """
        user_profile = UserInvestmentProfile.query.filter_by(user_id=user_id).first()
        
        if user_profile:
            user_profile.custom_overrides = {}
            user_profile.updated_at = now_utc()
            db.session.commit()
            logger.info(f"Reset user {user_id} to profile defaults")
        
        return user_profile
    
    # ============================================
    # PROFILE QUERIES
    # ============================================
    
    @classmethod
    def get_available_profiles(cls) -> List[Dict[str, Any]]:
        """Get all active investor profiles for selection UI."""
        profiles = InvestorProfile.query.filter_by(is_active=True).order_by(
            InvestorProfile.sort_order
        ).all()
        
        return [p.to_dict() for p in profiles]
    
    @classmethod
    def get_user_profile_info(cls, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user's current profile info for display.
        """
        user_profile = cls._get_user_profile(user_id)
        
        if not user_profile:
            return None
        
        return {
            'profile': user_profile.profile.to_dict() if user_profile.profile else None,
            'custom_overrides': user_profile.custom_overrides or {},
            'custom_override_count': len(user_profile.custom_overrides or {}),
            'years_experience': user_profile.years_experience,
            'investment_style': user_profile.investment_style,
            'risk_tolerance': user_profile.risk_tolerance
        }
    
    # ============================================
    # ADMIN / SYSTEM CONFIG MANAGEMENT
    # ============================================
    
    @classmethod
    def update_system_default(
        cls,
        key: str,
        value: Any,
        description: Optional[str] = None
    ) -> SystemConfig:
        """
        Update a system default value (admin only).
        """
        config = SystemConfig.query.filter_by(key=key).first()
        
        if not config:
            raise ValueError(f"Config key '{key}' not found")
        
        config.value = value
        if description:
            config.description = description
        config.updated_at = now_utc()
        
        db.session.commit()
        
        # Invalidate cache
        cls._invalidate_cache()
        
        logger.info(f"Updated system default: {key}={value}")
        return config
    
    @classmethod
    def get_all_system_configs(cls) -> List[Dict[str, Any]]:
        """Get all system configs for admin dashboard."""
        configs = SystemConfig.query.order_by(
            SystemConfig.category,
            SystemConfig.key
        ).all()
        
        return [c.to_dict() for c in configs]
    
    @classmethod
    def get_configs_by_category(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Get system configs grouped by category."""
        configs = SystemConfig.query.order_by(SystemConfig.key).all()
        
        by_category = {}
        for config in configs:
            category = config.category or 'uncategorized'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(config.to_dict())
        
        return by_category
    
    # ============================================
    # PRIVATE HELPERS
    # ============================================
    
    @classmethod
    def _get_system_default(cls, key: str) -> Any:
        """Get system default from cache or database."""
        cls._refresh_cache_if_needed()
        return cls._system_cache.get(key)
    
    @classmethod
    def _get_all_system_defaults(cls) -> Dict[str, Any]:
        """Get all system defaults."""
        cls._refresh_cache_if_needed()
        return cls._system_cache.copy()
    
    @classmethod
    def _refresh_cache_if_needed(cls) -> None:
        """Refresh system config cache if stale."""
        now = now_utc()
        
        if (cls._cache_timestamp is None or 
            (now - cls._cache_timestamp).total_seconds() > cls._cache_ttl_seconds):
            
            configs = SystemConfig.query.all()
            cls._system_cache = {c.key: c.value for c in configs}
            cls._cache_timestamp = now
            logger.debug("Refreshed system config cache")
    
    @classmethod
    def _invalidate_cache(cls) -> None:
        """Force cache refresh on next access."""
        cls._cache_timestamp = None
    
    @classmethod
    def _get_user_profile(cls, user_id: int) -> Optional[UserInvestmentProfile]:
        """Get user's investment profile."""
        return UserInvestmentProfile.query.filter_by(user_id=user_id).first()
    
    @classmethod
    def _get_category_keys(cls, category: str) -> List[str]:
        """Get all config keys for a category."""
        configs = SystemConfig.query.filter_by(category=category).all()
        return [c.key for c in configs]
    
    @classmethod
    def _determine_source(cls, key: str, user_id: Optional[int]) -> str:
        """Determine where the effective value comes from."""
        if user_id is None:
            return 'system'
        
        user_profile = cls._get_user_profile(user_id)
        
        if user_profile is None:
            return 'system'
        
        if user_profile.custom_overrides and key in user_profile.custom_overrides:
            return 'custom'
        
        if user_profile.profile and user_profile.profile.config_overrides:
            if key in user_profile.profile.config_overrides:
                return 'profile'
        
        return 'system'


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def get_config(key: str, user_id: Optional[int] = None, default: Any = None) -> Any:
    """
    Shorthand for ConfigService.get()
    
    Usage:
        from app.services.config_service import get_config
        threshold = get_config('concentration_warning_pct', user_id=current_user.id)
    """
    return ConfigService.get(key, user_id, default)


def get_user_config(user_id: int) -> Dict[str, Any]:
    """
    Shorthand for ConfigService.get_user_config()
    
    Usage:
        from app.services.config_service import get_user_config
        config = get_user_config(current_user.id)
    """
    return ConfigService.get_user_config(user_id)


# ============================================
# CONFIG KEY CONSTANTS (for IDE autocomplete)
# ============================================

class ConfigKeys:
    """Constants for config keys to avoid typos."""
    
    # Research Quality
    MIN_TIME_MINUTES = 'min_time_minutes'
    MIN_QUESTIONS_PCT = 'min_questions_pct'
    GOOD_ANSWER_LENGTH = 'good_answer_length'
    IDEAL_DOCUMENTS = 'ideal_documents'
    
    # Outcome Tracking
    BIG_WIN_THRESHOLD = 'big_win_threshold'
    BIG_LOSS_THRESHOLD = 'big_loss_threshold'
    MIN_OUTCOMES_FOR_ANALYSIS = 'min_outcomes_for_analysis'
    
    # Portfolio Alerts
    CONCENTRATION_WARNING_PCT = 'concentration_warning_pct'
    SECTOR_CONCENTRATION_PCT = 'sector_concentration_pct'
    INDUSTRY_CONCENTRATION_PCT = 'industry_concentration_pct'
    CORRELATION_THRESHOLD = 'correlation_threshold'
    MIN_RESEARCH_SCORE = 'min_research_score'
    
    # Behavioral Patterns
    MIN_HOLD_DAYS_FOR_PATTERN = 'min_hold_days_for_pattern'
    OVERCONFIDENCE_THRESHOLD = 'overconfidence_threshold'
    SELLING_WINNERS_EARLY_PCT = 'selling_winners_early_pct'
    HOLDING_LOSERS_THRESHOLD_PCT = 'holding_losers_threshold_pct'
    AVERAGING_DOWN_COUNT = 'averaging_down_count'
    
    # Thesis Analysis
    MIN_THESIS_LENGTH = 'min_thesis_length'
    THESIS_QUALITY_WARNING = 'thesis_quality_warning'
    MAX_KEY_ASSUMPTIONS = 'max_key_assumptions'
    
    # Similar Mistakes
    SIMILARITY_THRESHOLD = 'similarity_threshold'
    MAX_SIMILAR_RESULTS = 'max_similar_results'