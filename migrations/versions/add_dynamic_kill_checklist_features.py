"""Add Dynamic Kill Checklist intelligence features

Revision ID: dynamic_kill_checklist_v1
Revises: 02c0d68cf3c2
Create Date: 2024-01-01 12:00:00.000000

This migration adds intelligent features to the Kill Checklist system:
- Enhanced KillCriterion model with effectiveness tracking
- New KillChecklistSuggestion model for optimization suggestions
- Support for mistake-driven criterion generation
- Automatic prioritization based on performance data

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'b9dec42c43a0'
branch_labels = None
depends_on = None


def upgrade():
    """Add Dynamic Kill Checklist intelligence features"""

    # 1. Add new fields to kill_criterion table
    print("Adding intelligence fields to kill_criterion table...")

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        # Effectiveness tracking fields
        batch_op.add_column(sa.Column('effectiveness_score', sa.Float(), nullable=True, default=0.0))
        batch_op.add_column(sa.Column('last_calculated', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('auto_suggested', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('source_mistake_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('last_used', sa.DateTime(timezone=True), nullable=True))

        # Add foreign key constraint to mistake_log
        batch_op.create_foreign_key(
            'fk_kill_criterion_source_mistake',
            'mistake_log',
            ['source_mistake_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # 2. Create kill_checklist_suggestion table
    print("Creating kill_checklist_suggestion table...")

    op.create_table('kill_checklist_suggestion',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kill_checklist_id', sa.Integer(), nullable=False),

        # Suggestion details
        sa.Column('suggestion_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),

        # Suggestion data (JSON format for flexibility)
        sa.Column('suggestion_data', sa.JSON(), nullable=False),

        # Performance prediction
        sa.Column('effectiveness_gain', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True, default=0.5),

        # Tracking
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                 server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),

        # Source information
        sa.Column('trigger_event', sa.String(length=100), nullable=True),
        sa.Column('source_data', sa.JSON(), nullable=True),

        # Foreign key constraints
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kill_checklist_id'], ['kill_checklist.id'], ondelete='CASCADE'),

        # Indexes for performance
        sa.Index('idx_suggestion_user_status', 'user_id', 'status'),
        sa.Index('idx_suggestion_checklist_status', 'kill_checklist_id', 'status'),
        sa.Index('idx_suggestion_created_at', 'created_at'),
        sa.Index('idx_suggestion_effectiveness', 'effectiveness_gain'),
    )

    # 3. Add check constraints for data validation
    print("Adding data validation constraints...")

    with op.batch_alter_table('kill_checklist_suggestion', schema=None) as batch_op:
        # Ensure valid suggestion types
        batch_op.create_check_constraint(
            'ck_suggestion_type',
            sa.Column('suggestion_type').in_([
                'reorder_criteria', 'add_criterion', 'remove_criterion',
                'modify_criterion', 'merge_criteria'
            ])
        )

        # Ensure valid status values
        batch_op.create_check_constraint(
            'ck_suggestion_status',
            sa.Column('status').in_(['pending', 'accepted', 'rejected', 'auto_applied'])
        )

        # Ensure confidence score is between 0 and 1
        batch_op.create_check_constraint(
            'ck_confidence_score_range',
            sa.and_(
                sa.Column('confidence_score') >= 0.0,
                sa.Column('confidence_score') <= 1.0
            )
        )

        # Ensure effectiveness gain is reasonable (between -50% and +100%)
        batch_op.create_check_constraint(
            'ck_effectiveness_gain_range',
            sa.and_(
                sa.Column('effectiveness_gain') >= -0.5,
                sa.Column('effectiveness_gain') <= 1.0
            )
        )

    # 4. Add indexes to existing tables for performance
    print("Adding performance indexes...")

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        batch_op.create_index('idx_kill_criterion_effectiveness', ['effectiveness_score'])
        batch_op.create_index('idx_kill_criterion_auto_suggested', ['auto_suggested'])
        batch_op.create_index('idx_kill_criterion_last_used', ['last_used'])

    with op.batch_alter_table('kill_checklist', schema=None) as batch_op:
        batch_op.create_index('idx_kill_checklist_evaluations', ['total_ideas_evaluated'])
        batch_op.create_index('idx_kill_checklist_updated', ['updated_at'])

    # 5. Initialize default values for existing records
    print("Initializing default values for existing records...")

    # Set created_at for existing criteria to current timestamp if null
    op.execute("""
        UPDATE kill_criterion
        SET created_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL
    """)

    # Set effectiveness_score to 0.0 for existing criteria
    op.execute("""
        UPDATE kill_criterion
        SET effectiveness_score = 0.0
        WHERE effectiveness_score IS NULL
    """)

    # Set auto_suggested to false for existing criteria
    op.execute("""
        UPDATE kill_criterion
        SET auto_suggested = false
        WHERE auto_suggested IS NULL
    """)

    print("Dynamic Kill Checklist migration completed successfully!")


def downgrade():
    """Remove Dynamic Kill Checklist intelligence features"""

    print("Removing Dynamic Kill Checklist features...")

    # 1. Drop the kill_checklist_suggestion table
    print("Dropping kill_checklist_suggestion table...")
    op.drop_table('kill_checklist_suggestion')

    # 2. Remove indexes from existing tables
    print("Removing performance indexes...")

    with op.batch_alter_table('kill_checklist', schema=None) as batch_op:
        batch_op.drop_index('idx_kill_checklist_updated')
        batch_op.drop_index('idx_kill_checklist_evaluations')

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        batch_op.drop_index('idx_kill_criterion_last_used')
        batch_op.drop_index('idx_kill_criterion_auto_suggested')
        batch_op.drop_index('idx_kill_criterion_effectiveness')

    # 3. Remove new fields from kill_criterion table
    print("Removing intelligence fields from kill_criterion table...")

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        # Remove foreign key constraint first
        batch_op.drop_constraint('fk_kill_criterion_source_mistake', type_='foreignkey')

        # Remove columns
        batch_op.drop_column('last_used')
        batch_op.drop_column('created_at')
        batch_op.drop_column('source_mistake_id')
        batch_op.drop_column('auto_suggested')
        batch_op.drop_column('last_calculated')
        batch_op.drop_column('effectiveness_score')

    print("Dynamic Kill Checklist migration rollback completed!")


# Migration utility functions
def create_sample_suggestions():
    """Create sample suggestions for testing (called manually if needed)"""

    # This function can be called manually to create sample data for testing
    # It's not part of the automatic migration

    sample_suggestions = [
        {
            'suggestion_type': 'reorder_criteria',
            'title': 'Optimize criterion order for better efficiency',
            'description': 'Moving high-performing criteria earlier could improve kill rate by 15%',
            'effectiveness_gain': 0.15,
            'confidence_score': 0.8
        },
        {
            'suggestion_type': 'add_criterion',
            'title': 'Add debt-to-equity ratio check',
            'description': 'Based on your recent investment mistakes, consider adding a debt ratio check',
            'effectiveness_gain': 0.12,
            'confidence_score': 0.7
        }
    ]

    print("Sample suggestions available for manual insertion if needed")


def validate_migration():
    """Validate that the migration was successful"""

    # Check if tables exist
    inspector = sa.inspect(op.get_bind())

    # Verify kill_checklist_suggestion table exists
    if 'kill_checklist_suggestion' not in inspector.get_table_names():
        raise Exception("kill_checklist_suggestion table was not created")

    # Verify new columns exist in kill_criterion
    kill_criterion_columns = [col['name'] for col in inspector.get_columns('kill_criterion')]
    required_columns = ['effectiveness_score', 'last_calculated', 'auto_suggested',
                       'source_mistake_id', 'created_at', 'last_used']

    for col in required_columns:
        if col not in kill_criterion_columns:
            raise Exception(f"Column {col} was not added to kill_criterion table")

    print("Migration validation successful!")


# This can be used for data migration if needed
def migrate_existing_data():
    """Migrate existing data to new format (if needed)"""

    # Calculate initial effectiveness scores for existing criteria
    # This could be done based on historical data

    op.execute("""
        UPDATE kill_criterion
        SET effectiveness_score = CASE
            WHEN times_evaluated > 0 THEN
                (CAST(times_failed AS FLOAT) / times_evaluated) * 0.5
            ELSE 0.0
        END
        WHERE effectiveness_score = 0.0 AND times_evaluated > 0
    """)

    print("Existing data migration completed")