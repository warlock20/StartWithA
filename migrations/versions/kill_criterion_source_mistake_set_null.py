"""kill_criterion.source_mistake_id: ON DELETE SET NULL

Deleting a mistake (or the company/account it belongs to) failed once a kill
criterion had been added from it. The criterion now outlives the mistake and
loses only the link.

Revision ID: kill_criterion_set_null_370
Revises: knowledge_index_389
Create Date: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa


revision = 'kill_criterion_set_null_370'
down_revision = 'knowledge_index_389'
branch_labels = None
depends_on = None

NEW_FK = 'fk_kill_criterion_source_mistake'


def _drop_existing_fks():
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys('kill_criterion'):
        if fk['constrained_columns'] == ['source_mistake_id'] and fk.get('name'):
            op.drop_constraint(fk['name'], 'kill_criterion', type_='foreignkey')


def upgrade():
    _drop_existing_fks()
    op.create_foreign_key(NEW_FK, 'kill_criterion', 'mistake_log',
                          ['source_mistake_id'], ['id'], ondelete='SET NULL')


def downgrade():
    _drop_existing_fks()
    op.create_foreign_key(NEW_FK, 'kill_criterion', 'mistake_log',
                          ['source_mistake_id'], ['id'])
