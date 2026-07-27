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

"""add user_ai_preference table

Revision ID: 644ee0c924cf
Revises: rename_free_to_amateur
Create Date: 2026-07-12 15:14:50.281601

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '644ee0c924cf'
down_revision = 'rename_free_to_amateur'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_ai_preference',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('prompt_category', sa.String(length=50), nullable=False),
    sa.Column('model_override', sa.String(length=100), nullable=True),
    sa.Column('provider_override', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'prompt_category', name='uq_user_prompt_category')
    )
    with op.batch_alter_table('user_ai_preference', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_ai_preference_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('user_ai_preference', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_ai_preference_user_id'))

    op.drop_table('user_ai_preference')
