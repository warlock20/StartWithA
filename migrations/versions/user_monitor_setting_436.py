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

"""user_monitor_setting: per-user background monitor schedules

Revision ID: user_monitor_setting_436
Revises: exit_plan_stale_config_435
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa


revision = 'user_monitor_setting_436'
down_revision = 'exit_plan_stale_config_435'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_monitor_setting',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('monitor_key', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('frequency', sa.String(length=10), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "frequency IS NULL OR frequency IN ('off','daily','weekly','monthly')",
            name='ck_user_monitor_setting_frequency'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'monitor_key', name='uq_user_monitor_setting_user_monitor'),
    )
    with op.batch_alter_table('user_monitor_setting', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_monitor_setting_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('user_monitor_setting', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_monitor_setting_user_id'))
    op.drop_table('user_monitor_setting')
