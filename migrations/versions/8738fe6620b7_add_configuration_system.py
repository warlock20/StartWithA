"""Add configuration system tables

Revision ID: 8738fe6620b7
Revises: 5cab725fd0d5
Create Date: 2026-01-02

Tables:
- system_config: System-wide configuration defaults
- investor_profile: Predefined investor profiles (beginner, intermediate, expert, pro)
- user_investment_profile: User's selected profile + custom overrides
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8738fe6620b7'
down_revision = '5cab725fd0d5'
branch_labels = None
depends_on = None


def upgrade():
    # ============================================
    # TABLE 1: system_config
    # ============================================
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('data_type', sa.String(20), default='number'),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_system_config_key', 'system_config', ['key'])
    op.create_index('ix_system_config_category', 'system_config', ['category'])

    # ============================================
    # TABLE 2: investor_profile
    # ============================================
    op.create_table(
        'investor_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config_overrides', sa.JSON(), nullable=False, default={}),
        sa.Column('icon', sa.String(50), default='user'),
        sa.Column('color', sa.String(20), default='primary'),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # ============================================
    # TABLE 3: user_investment_profile
    # ============================================
    op.create_table(
        'user_investment_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('custom_overrides', sa.JSON(), default={}),
        sa.Column('years_experience', sa.Integer(), nullable=True),
        sa.Column('investment_style', sa.String(50), nullable=True),
        sa.Column('risk_tolerance', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['profile_id'], ['investor_profile.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_investment_profile_user_id', 'user_investment_profile', ['user_id'])

    # ============================================
    # SEED DATA: Default System Config
    # ============================================
    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at) VALUES
        -- Research Quality
        ('min_time_minutes', '30', 'Minimum research time (minutes) for good score', 'research_quality', 'number', 5, 480, NOW(), NOW()),
        ('min_questions_pct', '70', 'Minimum % of questions to answer', 'research_quality', 'percent', 20, 100, NOW(), NOW()),
        ('good_answer_length', '200', 'Character count for quality answers', 'research_quality', 'number', 50, 1000, NOW(), NOW()),
        ('ideal_documents', '5', 'Number of documents for thorough research', 'research_quality', 'number', 1, 20, NOW(), NOW()),

        -- Outcome Tracking
        ('big_win_threshold', '25', 'Return % to count as big win', 'outcome_tracking', 'percent', 5, 100, NOW(), NOW()),
        ('big_loss_threshold', '15', 'Loss % to count as big loss', 'outcome_tracking', 'percent', 5, 50, NOW(), NOW()),
        ('min_outcomes_for_analysis', '3', 'Minimum completed trades for correlation', 'outcome_tracking', 'number', 1, 20, NOW(), NOW()),

        -- Portfolio Alerts
        ('concentration_warning_pct', '25', 'Single position % to trigger warning', 'portfolio_alerts', 'percent', 5, 50, NOW(), NOW()),
        ('sector_concentration_pct', '40', 'Sector % to trigger warning', 'portfolio_alerts', 'percent', 10, 80, NOW(), NOW()),
        ('industry_concentration_pct', '30', 'Industry % to trigger warning', 'portfolio_alerts', 'percent', 10, 60, NOW(), NOW()),
        ('correlation_threshold', '0.7', 'Correlation coefficient for warning', 'portfolio_alerts', 'number', 0.3, 1.0, NOW(), NOW()),
        ('min_research_score', '50', 'Minimum research score before warning', 'portfolio_alerts', 'number', 0, 100, NOW(), NOW()),

        -- Behavioral Patterns
        ('min_hold_days_for_pattern', '30', 'Minimum hold days for pattern analysis', 'behavioral_patterns', 'number', 7, 365, NOW(), NOW()),
        ('overconfidence_threshold', '8', 'Confidence level (1-10) to flag as high', 'behavioral_patterns', 'number', 5, 10, NOW(), NOW()),
        ('selling_winners_early_pct', '10', 'Gain % at which selling is too early', 'behavioral_patterns', 'percent', 5, 50, NOW(), NOW()),
        ('holding_losers_threshold_pct', '20', 'Loss % to flag as holding too long', 'behavioral_patterns', 'percent', 5, 50, NOW(), NOW()),
        ('averaging_down_count', '2', 'Number of buys to flag averaging down', 'behavioral_patterns', 'number', 2, 10, NOW(), NOW()),

        -- Thesis Analysis
        ('min_thesis_length', '100', 'Minimum characters for valid thesis', 'thesis_analysis', 'number', 20, 500, NOW(), NOW()),
        ('thesis_quality_warning', '60', 'Score below which to warn', 'thesis_analysis', 'number', 0, 100, NOW(), NOW()),
        ('max_key_assumptions', '5', 'Number of key assumptions to identify', 'thesis_analysis', 'number', 3, 10, NOW(), NOW()),

        -- Similar Mistakes
        ('similarity_threshold', '0.7', 'Cosine similarity threshold for matching', 'similar_mistakes', 'number', 0.5, 0.95, NOW(), NOW()),
        ('max_similar_results', '5', 'Maximum similar decisions to show', 'similar_mistakes', 'number', 1, 10, NOW(), NOW())
    """)

    # ============================================
    # SEED DATA: Investor Profiles
    # ============================================
    op.execute("""
        INSERT INTO investor_profile (name, display_name, description, config_overrides, icon, color, sort_order, is_active, created_at, updated_at) VALUES
        (
            'beginner',
            'Beginner Investor',
            'New to investing. Lenient thresholds with more encouragement and guidance.',
            '{
                "min_time_minutes": 15,
                "min_questions_pct": 50,
                "good_answer_length": 100,
                "big_win_threshold": 15,
                "big_loss_threshold": 10,
                "min_outcomes_for_analysis": 2,
                "concentration_warning_pct": 30,
                "sector_concentration_pct": 50,
                "min_research_score": 40,
                "thesis_quality_warning": 50
            }',
            'seedling',
            'success',
            1,
            true,
            NOW(),
            NOW()
        ),
        (
            'intermediate',
            'Intermediate Investor',
            '1-3 years experience. Balanced thresholds for steady improvement.',
            '{
                "min_time_minutes": 30,
                "min_questions_pct": 70,
                "good_answer_length": 200,
                "big_win_threshold": 25,
                "big_loss_threshold": 15,
                "min_outcomes_for_analysis": 3,
                "concentration_warning_pct": 25,
                "sector_concentration_pct": 40,
                "min_research_score": 50,
                "thesis_quality_warning": 60
            }',
            'chart-line',
            'primary',
            2,
            true,
            NOW(),
            NOW()
        ),
        (
            'expert',
            'Expert Investor',
            '3+ years experience. Stricter standards for serious investors.',
            '{
                "min_time_minutes": 60,
                "min_questions_pct": 85,
                "good_answer_length": 300,
                "big_win_threshold": 30,
                "big_loss_threshold": 20,
                "min_outcomes_for_analysis": 5,
                "concentration_warning_pct": 20,
                "sector_concentration_pct": 35,
                "min_research_score": 60,
                "thesis_quality_warning": 70
            }',
            'trophy',
            'warning',
            3,
            true,
            NOW(),
            NOW()
        ),
        (
            'professional',
            'Professional / Fund Manager',
            'Managing money professionally. Very strict standards with comprehensive data requirements.',
            '{
                "min_time_minutes": 120,
                "min_questions_pct": 95,
                "good_answer_length": 500,
                "big_win_threshold": 40,
                "big_loss_threshold": 25,
                "min_outcomes_for_analysis": 10,
                "concentration_warning_pct": 15,
                "sector_concentration_pct": 30,
                "min_research_score": 70,
                "thesis_quality_warning": 80
            }',
            'briefcase',
            'danger',
            4,
            true,
            NOW(),
            NOW()
        )
    """)


def downgrade():
    op.drop_table('user_investment_profile')
    op.drop_table('investor_profile')
    op.drop_table('system_config')
