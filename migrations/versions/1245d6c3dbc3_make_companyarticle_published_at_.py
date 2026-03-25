"""Make CompanyArticle.published_at nullable and url non-unique

Revision ID: 1245d6c3dbc3
Revises: e059bebc4087
Create Date: 2026-03-23 15:59:47.388566

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1245d6c3dbc3'
down_revision = 'e059bebc4087'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('company_article', schema=None) as batch_op:
        batch_op.alter_column('published_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.drop_constraint('company_article_url_key', type_='unique')


def downgrade():
    with op.batch_alter_table('company_article', schema=None) as batch_op:
        batch_op.create_unique_constraint('company_article_url_key', ['url'])
        batch_op.alter_column('published_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
