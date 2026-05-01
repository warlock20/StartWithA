"""
Feature Unlock Service

Handles usage-based automatic unlocking of feature groups,
badge state management, and admin override operations.
"""

import logging
from app import db
from app.models import IdeaPipeline, Company, ResearchProject
from app.models.portfolio import PortfolioPosition
from app.models.configuration import SystemConfig
from app.features import FEATURE_GROUPS, FEATURE_TO_GROUP
from app.utils.time_utils import now_utc
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)


# Maps each group to how its unlock metric is computed and its fallback threshold.
UNLOCK_CONFIG = {
    'research_tools': {
        'metric': lambda uid: IdeaPipeline.query.filter(
            IdeaPipeline.user_id == uid,
            IdeaPipeline.status != 'inbox',
        ).count(),
        'default_threshold': 5,
        'config_key': 'unlock_threshold_research_tools',
        'description': 'Ideas evaluated (status != inbox) to unlock Research Tools',
    },
    'advanced_research': {
        'metric': lambda uid: Company.query.filter_by(user_id=uid).count(),
        'default_threshold': 5,
        'config_key': 'unlock_threshold_advanced_research',
        'description': 'Companies created to unlock Advanced Research',
    },
    'portfolio_intelligence': {
        'metric': lambda uid: PortfolioPosition.query.filter_by(
            user_id=uid, is_active=True,
        ).count(),
        'default_threshold': 3,
        'config_key': 'unlock_threshold_portfolio_intelligence',
        'description': 'Active portfolio positions to unlock Portfolio Intelligence',
    },
    'knowledge_learning': {
        'metric': lambda uid: ResearchProject.query.filter(
            ResearchProject.user_id == uid,
            ResearchProject.decision.isnot(None),
        ).count(),
        'default_threshold': 3,
        'config_key': 'unlock_threshold_knowledge_learning',
        'description': 'Research projects with decisions to unlock Knowledge & Learning',
    },
}


class FeatureUnlockService:
    """Service for managing feature group unlocks."""

    @staticmethod
    def check_and_unlock(user):
        """
        Check all unlock groups and unlock any where the user meets the threshold.

        Returns list of newly unlocked group names (empty if none).
        """
        unlocked = user.unlocked_features or {}
        newly = user.newly_unlocked_features or {}
        newly_unlocked = []

        for group_name, config in UNLOCK_CONFIG.items():
            # Skip already-unlocked groups
            if group_name in unlocked:
                continue

            # Read threshold from SystemConfig, fall back to default
            threshold = config['default_threshold']
            sys_config = SystemConfig.query.filter_by(
                key=config['config_key']
            ).first()
            if sys_config and sys_config.value is not None:
                threshold = int(sys_config.value)

            # Check metric
            count = config['metric'](user.id)
            if count >= threshold:
                timestamp = now_utc().isoformat()
                unlocked[group_name] = timestamp
                newly[group_name] = timestamp
                newly_unlocked.append(group_name)
                logger.info(
                    'User %s unlocked group %s (count=%d, threshold=%d)',
                    user.id, group_name, count, threshold,
                )

        if newly_unlocked:
            user.unlocked_features = unlocked
            user.newly_unlocked_features = newly
            flag_modified(user, 'unlocked_features')
            flag_modified(user, 'newly_unlocked_features')
            db.session.commit()

        return newly_unlocked

    @staticmethod
    def dismiss_new_badge(user, group_name):
        """Remove a group from newly_unlocked_features (hides the NEW badge)."""
        newly = user.newly_unlocked_features or {}
        if group_name in newly:
            del newly[group_name]
            user.newly_unlocked_features = newly
            flag_modified(user, 'newly_unlocked_features')
            db.session.commit()

    @staticmethod
    def get_unlock_progress(user):
        """Return progress data for groups not yet unlocked."""
        unlocked = user.unlocked_features or {}
        progress = []
        for group_name, config in UNLOCK_CONFIG.items():
            if group_name in unlocked:
                continue
            threshold = config['default_threshold']
            sys_config = SystemConfig.query.filter_by(
                key=config['config_key']
            ).first()
            if sys_config and sys_config.value is not None:
                threshold = int(sys_config.value)
            count = config['metric'](user.id)
            progress.append({
                'group': group_name,
                'label': group_name.replace('_', ' ').title(),
                'count': min(count, threshold),
                'threshold': threshold,
                'percent': min(100, int(count / threshold * 100)) if threshold > 0 else 0,
            })
        return progress

    @staticmethod
    def admin_unlock_group(user, group_name):
        """Manually unlock an entire feature group for a user."""
        if group_name not in FEATURE_GROUPS:
            raise ValueError(f'Unknown group: {group_name}')
        unlocked = user.unlocked_features or {}
        unlocked[group_name] = now_utc().isoformat()
        user.unlocked_features = unlocked
        flag_modified(user, 'unlocked_features')
        db.session.commit()

    @staticmethod
    def admin_lock_group(user, group_name):
        """Revoke a feature group from a user."""
        unlocked = user.unlocked_features or {}
        unlocked.pop(group_name, None)
        user.unlocked_features = unlocked
        flag_modified(user, 'unlocked_features')
        # Also clear badge state
        newly = user.newly_unlocked_features or {}
        newly.pop(group_name, None)
        user.newly_unlocked_features = newly
        flag_modified(user, 'newly_unlocked_features')
        db.session.commit()

    @staticmethod
    def admin_unlock_feature(user, feature_name):
        """Manually unlock a single feature for a user."""
        unlocked = user.unlocked_features or {}
        unlocked[feature_name] = now_utc().isoformat()
        user.unlocked_features = unlocked
        flag_modified(user, 'unlocked_features')
        db.session.commit()

    @staticmethod
    def admin_lock_feature(user, feature_name):
        """Revoke a single feature from a user."""
        unlocked = user.unlocked_features or {}
        unlocked.pop(feature_name, None)
        user.unlocked_features = unlocked
        flag_modified(user, 'unlocked_features')
        db.session.commit()


def seed_unlock_thresholds():
    """Seed SystemConfig with default unlock thresholds for each feature group."""
    for group_name, config in UNLOCK_CONFIG.items():
        existing = SystemConfig.query.filter_by(key=config['config_key']).first()
        if existing:
            logger.info('Threshold %s already exists (value=%s), skipping',
                        config['config_key'], existing.value)
            continue
        entry = SystemConfig(
            key=config['config_key'],
            value=config['default_threshold'],
            description=config['description'],
            category='feature_unlocks',
            data_type='number',
            min_value=1,
            max_value=100,
        )
        db.session.add(entry)
        logger.info('Seeded %s = %d', config['config_key'], config['default_threshold'])
    db.session.commit()
