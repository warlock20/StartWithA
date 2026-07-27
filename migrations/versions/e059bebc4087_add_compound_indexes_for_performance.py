"""add compound indexes for performance

Revision ID: e059bebc4087
Revises: 8a4e335a947a
Create Date: 2026-03-20 21:37:04.107311

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e059bebc4087'
down_revision = '8a4e335a947a'
branch_labels = None
depends_on = None


def upgrade():
    # Compound indexes for frequent query patterns

    # Company: dashboard filter_by(user_id=..., is_in_portfolio=True)
    op.create_index(
        'idx_company_user_portfolio',
        'company', ['user_id', 'is_in_portfolio']
    )

    # IdeaPipeline: dashboard + too-hard filter_by(user_id=..., status='killed')
    op.create_index(
        'idx_idea_pipeline_user_status',
        'idea_pipeline', ['user_id', 'status']
    )

    # ResearchProject: too-hard service filter_by(user_id=..., decision='pass')
    op.create_index(
        'idx_research_project_user_decision',
        'research_project', ['user_id', 'decision']
    )

    # ResearchProject: priority service filter_by(user_id=..., status='active')
    op.create_index(
        'idx_research_project_user_status',
        'research_project', ['user_id', 'status']
    )

    # PortfolioPosition: portfolio dashboard filter_by(user_id=..., is_active=True)
    op.create_index(
        'idx_portfolio_position_user_active',
        'portfolio_position', ['user_id', 'is_active']
    )

    # KillSession: analytics filter_by(user_id=current_user.id)
    op.create_index(
        'idx_kill_session_user',
        'kill_session', ['user_id']
    )

    # WeeklyReview: learning streak calculation filter_by(user_id=...) + week_start
    op.create_index(
        'idx_weekly_review_user_week',
        'weekly_review', ['user_id', 'week_start']
    )

    # WorkSession: time allocation filter(user_id=..., start_time >= ...)
    op.create_index(
        'idx_work_session_user_start',
        'work_session', ['user_id', 'start_time']
    )

    # ResearchLog: streak calculation filter(user_id=...) + timestamp
    op.create_index(
        'idx_research_log_user_timestamp',
        'research_log', ['user_id', 'timestamp']
    )


def downgrade():
    op.drop_index('idx_research_log_user_timestamp', 'research_log')
    op.drop_index('idx_work_session_user_start', 'work_session')
    op.drop_index('idx_weekly_review_user_week', 'weekly_review')
    op.drop_index('idx_kill_session_user', 'kill_session')
    op.drop_index('idx_portfolio_position_user_active', 'portfolio_position')
    op.drop_index('idx_research_project_user_status', 'research_project')
    op.drop_index('idx_research_project_user_decision', 'research_project')
    op.drop_index('idx_idea_pipeline_user_status', 'idea_pipeline')
    op.drop_index('idx_company_user_portfolio', 'company')
