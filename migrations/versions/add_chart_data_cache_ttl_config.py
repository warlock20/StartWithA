"""Add chart_data_cache_ttl_hours system config

Revision ID: c3a7f1d82e49
Revises: b5f37db73215
Create Date: 2026-02-07

Adds a configurable TTL (in hours) for cached chart data on the analytics page.
Default: 24 hours. Editable from the admin panel.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c3a7f1d82e49'
down_revision = 'b5f37db73215'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at)
        VALUES (
            'chart_data_cache_ttl_hours',
            '24',
            'Hours to cache Performance vs Cost chart data before refreshing from price APIs',
            'performance',
            'number',
            1,
            168,
            NOW(),
            NOW()
        )
    """)


def downgrade():
    op.execute("DELETE FROM system_config WHERE key = 'chart_data_cache_ttl_hours'")
