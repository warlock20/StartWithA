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

"""scheduled job run history (#397)

Celery keeps no history of beat job runs, so whether the GDPR anonymisation,
checkpoint analysis or AI-check reaper ran could only be read from Railway
logs. Each scheduled task now writes one row per run, which the admin
"Scheduled jobs" page reads. Rows older than 90 days are pruned by a job of
their own.

Revision ID: scheduled_job_run
Revises: e5b1467ec086
Create Date: 2026-10-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'scheduled_job_run'
down_revision = 'e5b1467ec086'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_job_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(length=20), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_job_run_job_started', 'scheduled_job_run',
                    ['job_name', 'started_at'], unique=False)


def downgrade():
    op.drop_index('ix_scheduled_job_run_job_started', table_name='scheduled_job_run')
    op.drop_table('scheduled_job_run')
