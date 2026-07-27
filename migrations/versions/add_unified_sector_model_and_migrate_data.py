"""Add unified Sector model and migrate existing sector data

Revision ID: add_unified_sector
Revises: 0b58d4f1ab37
Create Date: 2025-10-18

This migration:
1. Creates the new 'sector' table as the master sector registry
2. Adds sector_id foreign keys to company, sector_analysis, research_project, idea_pipeline
3. Migrates existing string-based sector data to new Sector records
4. Updates all foreign key references
5. Removes old string-based sector columns

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_unified_sector'
down_revision = '0b58d4f1ab37'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create the new sector table
    op.create_table(
        'sector',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('aliases', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('parent_sector_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_characteristics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('typical_metrics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('merged_into_id', sa.Integer(), nullable=True),
        sa.Column('total_companies', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('companies_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('companies_invested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_research_hours', sa.Float(), nullable=False, server_default='0'),
        sa.Column('coc_yes_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coc_no_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coc_unsure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_researched', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['merged_into_id'], ['sector.id'], ),
        sa.ForeignKeyConstraint(['parent_sector_id'], ['sector.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'slug', name='_user_sector_slug_uc')
    )

    # Create indexes
    op.create_index('idx_sector_user_id', 'sector', ['user_id'], unique=False)
    op.create_index('idx_sector_slug', 'sector', ['slug'], unique=False)
    op.create_index('idx_sector_status', 'sector', ['status'], unique=False)
    op.create_index('idx_sector_category', 'sector', ['category'], unique=False)

    # 2. Add sector_id columns to related tables (nullable initially for migration)
    op.add_column('company', sa.Column('sector_id', sa.Integer(), nullable=True))
    op.add_column('sector_analysis', sa.Column('sector_id', sa.Integer(), nullable=True))
    op.add_column('research_project', sa.Column('sector_id', sa.Integer(), nullable=True))
    op.add_column('idea_pipeline', sa.Column('sector_id', sa.Integer(), nullable=True))
    op.add_column('question_bank_item', sa.Column('sector_id', sa.Integer(), nullable=True))

    # 3. Migrate existing sector data
    bind = op.get_bind()
    session = Session(bind=bind)

    # Helper function to create slug
    def make_slug(name):
        import re
        import unicodedata
        if not name:
            return 'uncategorized'
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return slug or 'uncategorized'

    # Collect all unique (user_id, sector_name) pairs from all tables
    unique_sectors = set()

    # From company table
    companies = session.execute(
        text("SELECT DISTINCT user_id, sector FROM company WHERE sector IS NOT NULL AND sector != ''")
    ).fetchall()
    for user_id, sector_name in companies:
        unique_sectors.add((user_id, sector_name))

    # From sector_analysis table
    analyses = session.execute(
        text("SELECT DISTINCT user_id, sector_name FROM sector_analysis WHERE sector_name IS NOT NULL AND sector_name != ''")
    ).fetchall()
    for user_id, sector_name in analyses:
        unique_sectors.add((user_id, sector_name))

    # From question_bank_item table (if sector column exists)
    try:
        questions = session.execute(
            text("SELECT DISTINCT user_id, sector FROM question_bank_item WHERE sector IS NOT NULL AND sector != ''")
        ).fetchall()
        for user_id, sector_name in questions:
            unique_sectors.add((user_id, sector_name))
    except:
        pass  # Column might not exist yet

    # Create Sector records and build mapping
    sector_mapping = {}  # (user_id, old_name) -> sector_id

    for user_id, sector_name in unique_sectors:
        slug = make_slug(sector_name)
        display_name = sector_name.title()

        # Check if slug already exists for this user (handle duplicates)
        existing = session.execute(
            text("SELECT id FROM sector WHERE user_id = :user_id AND slug = :slug"),
            {'user_id': user_id, 'slug': slug}
        ).fetchone()

        if existing:
            sector_id = existing[0]
        else:
            # Insert new sector
            result = session.execute(
                text("""
                INSERT INTO sector (user_id, name, display_name, slug, is_default, created_at, updated_at)
                VALUES (:user_id, :name, :display_name, :slug, :is_default, :created_at, :updated_at)
                RETURNING id
                """),
                {
                    'user_id': user_id,
                    'name': sector_name,
                    'display_name': display_name,
                    'slug': slug,
                    'is_default': False,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            )
            sector_id = result.fetchone()[0]

        sector_mapping[(user_id, sector_name)] = sector_id

    session.commit()

    # 4. Update foreign keys in related tables
    for (user_id, old_name), sector_id in sector_mapping.items():
        # Update company table
        session.execute(
            text("UPDATE company SET sector_id = :sector_id WHERE user_id = :user_id AND sector = :old_name"),
            {'sector_id': sector_id, 'user_id': user_id, 'old_name': old_name}
        )

        # Update sector_analysis table
        session.execute(
            text("UPDATE sector_analysis SET sector_id = :sector_id WHERE user_id = :user_id AND sector_name = :old_name"),
            {'sector_id': sector_id, 'user_id': user_id, 'old_name': old_name}
        )

        # Update question_bank_item table (if column exists)
        try:
            session.execute(
                text("UPDATE question_bank_item SET sector_id = :sector_id WHERE user_id = :user_id AND sector = :old_name"),
                {'sector_id': sector_id, 'user_id': user_id, 'old_name': old_name}
            )
        except:
            pass

    session.commit()

    # 5. Add foreign key constraints
    op.create_foreign_key('fk_company_sector', 'company', 'sector', ['sector_id'], ['id'])
    op.create_foreign_key('fk_sector_analysis_sector', 'sector_analysis', 'sector', ['sector_id'], ['id'])
    op.create_foreign_key('fk_research_project_sector', 'research_project', 'sector', ['sector_id'], ['id'])
    op.create_foreign_key('fk_idea_pipeline_sector', 'idea_pipeline', 'sector', ['sector_id'], ['id'])
    op.create_foreign_key('fk_question_bank_item_sector', 'question_bank_item', 'sector', ['sector_id'], ['id'])

    # Create indexes for performance
    op.create_index('idx_company_sector', 'company', ['sector_id'], unique=False)
    op.create_index('idx_research_project_sector', 'research_project', ['sector_id'], unique=False)
    op.create_index('idx_idea_pipeline_sector', 'idea_pipeline', ['sector_id'], unique=False)
    op.create_index('idx_question_bank_item_sector', 'question_bank_item', ['sector_id'], unique=False)

    # 6. Drop old string-based sector columns (after data migration)
    op.drop_column('company', 'sector')

    # Drop old unique constraint on sector_analysis before dropping column
    op.drop_constraint('uq_user_sector', 'sector_analysis', type_='unique')
    op.drop_column('sector_analysis', 'sector_name')

    # Add new unique constraint on sector_id
    op.create_unique_constraint('uq_user_sector_id', 'sector_analysis', ['user_id', 'sector_id'])

    # Drop sector column from question_bank_item if it exists
    try:
        op.drop_column('question_bank_item', 'sector')
    except:
        pass  # Column might not exist


def downgrade():
    # Reverse migration - restore string-based sectors

    # 1. Re-add string columns
    op.add_column('company', sa.Column('sector', sa.String(length=100), nullable=True))
    op.add_column('sector_analysis', sa.Column('sector_name', sa.String(length=100), nullable=True))
    op.add_column('question_bank_item', sa.Column('sector', sa.String(length=100), nullable=True))

    # 2. Copy data back from Sector table
    bind = op.get_bind()
    session = Session(bind=bind)

    # Restore company sectors
    session.execute(text("""
        UPDATE company c
        SET sector = s.name
        FROM sector s
        WHERE c.sector_id = s.id
    """))

    # Restore sector_analysis sectors
    session.execute(text("""
        UPDATE sector_analysis sa
        SET sector_name = s.name
        FROM sector s
        WHERE sa.sector_id = s.id
    """))

    # Restore question_bank_item sectors
    try:
        session.execute(text("""
            UPDATE question_bank_item q
            SET sector = s.name
            FROM sector s
            WHERE q.sector_id = s.id
        """))
    except:
        pass

    session.commit()

    # 3. Drop new constraint and restore old one
    op.drop_constraint('uq_user_sector_id', 'sector_analysis', type_='unique')
    op.create_unique_constraint('uq_user_sector', 'sector_analysis', ['user_id', 'sector_name'])

    # 4. Drop indexes
    op.drop_index('idx_company_sector', table_name='company')
    op.drop_index('idx_research_project_sector', table_name='research_project')
    op.drop_index('idx_idea_pipeline_sector', table_name='idea_pipeline')
    op.drop_index('idx_question_bank_item_sector', table_name='question_bank_item')

    # 5. Drop foreign key constraints
    op.drop_constraint('fk_company_sector', 'company', type_='foreignkey')
    op.drop_constraint('fk_sector_analysis_sector', 'sector_analysis', type_='foreignkey')
    op.drop_constraint('fk_research_project_sector', 'research_project', type_='foreignkey')
    op.drop_constraint('fk_idea_pipeline_sector', 'idea_pipeline', type_='foreignkey')
    op.drop_constraint('fk_question_bank_item_sector', 'question_bank_item', type_='foreignkey')

    # 6. Drop sector_id columns
    op.drop_column('question_bank_item', 'sector_id')
    op.drop_column('idea_pipeline', 'sector_id')
    op.drop_column('research_project', 'sector_id')
    op.drop_column('sector_analysis', 'sector_id')
    op.drop_column('company', 'sector_id')

    # 7. Drop sector table indexes
    op.drop_index('idx_sector_category', table_name='sector')
    op.drop_index('idx_sector_status', table_name='sector')
    op.drop_index('idx_sector_slug', table_name='sector')
    op.drop_index('idx_sector_user_id', table_name='sector')

    # 8. Drop sector table
    op.drop_table('sector')
