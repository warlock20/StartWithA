"""
Feature gating system for progressive disclosure.

Single source of truth for which features are visible to which users.
Features not listed here default to 'core' (always visible).
"""

# Maps feature keys to their required tier.
# 'core' = visible to everyone, 'pro' = hidden for free users.
FEATURE_TIERS = {
    # Research
    'sectors': 'pro',
    'start_with_a': 'pro',
    'analytics': 'pro',
    'research_templates': 'pro',
    'kill_checklists': 'pro',
    'investment_checklists': 'pro',
    'question_bank': 'pro',
    'company_directory': 'core',

    # Portfolio
    'portfolio_intelligence': 'pro',
    'portfolio_journal': 'pro',

    # Knowledge
    'knowledge_hub': 'pro',
    'learning_dashboard': 'pro',
    'learning_paths': 'pro',
    'mistake_log': 'pro',
    'weekly_review': 'pro',
}

# Which tiers can see which feature levels
TIER_ACCESS = {
    'free': ['core'],
    'pro': ['core', 'pro'],
    'beta_tester': ['core', 'pro'],
}

# Feature unlock groups — features unlock together as a bundle.
# When a group is unlocked, ALL features in it become available.
FEATURE_GROUPS = {
    'research_tools': [
        'research_templates', 'kill_checklists',
        'investment_checklists', 'question_bank',
    ],
    'advanced_research': [
        'sectors', 'start_with_a', 'analytics',
    ],
    'portfolio_intelligence': [
        'portfolio_intelligence', 'portfolio_journal',
    ],
    'knowledge_learning': [
        'knowledge_hub', 'learning_dashboard', 'learning_paths',
        'mistake_log', 'weekly_review',
    ],
}

# Reverse lookup: feature_name → group_name
FEATURE_TO_GROUP = {}
for _group, _features in FEATURE_GROUPS.items():
    for _feat in _features:
        FEATURE_TO_GROUP[_feat] = _group


def user_has_feature(user, feature_name):
    """
    Check if a user can access a given feature.

    Returns True if ANY of these conditions is met:
    1. The feature is 'core' tier (always visible)
    2. The user's subscription_tier grants access
    3. The user has toggled 'show_advanced_features'
    4. The feature was individually unlocked for this user
    5. The feature's unlock group was unlocked for this user
    """
    feature_tier = FEATURE_TIERS.get(feature_name, 'core')

    # Core features are always visible
    if feature_tier == 'core':
        return True

    # Check subscription tier
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    allowed_tiers = TIER_ACCESS.get(tier, ['core'])
    if feature_tier in allowed_tiers:
        return True

    # Check manual toggle
    if getattr(user, 'show_advanced_features', False):
        return True

    # Check individually unlocked features or group-level unlocks
    unlocked = getattr(user, 'unlocked_features', None) or {}
    if feature_name in unlocked:
        return True

    group = FEATURE_TO_GROUP.get(feature_name)
    if group and group in unlocked:
        return True

    return False
