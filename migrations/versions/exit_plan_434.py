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

"""exit plans (#434): must-exit rules always have a company, top-up and
imported markers on decisions and transactions, exit_criteria as a JSON snapshot

Revision ID: exit_plan_434
Revises: watchlist_target_237
Create Date: 2026-11-20
"""
import json

from alembic import op
import sqlalchemy as sa

from app.utils.blocknote_utils import blocknote_to_text
from app.utils.time_utils import now_utc


revision = 'exit_plan_434'
down_revision = 'watchlist_target_237'
branch_labels = None
depends_on = None

# Frozen copies of app values, so later changes in the app don't change this migration.
IMPORTED_BUY_THESIS = 'Imported via bulk uploader'
IMPORTED_NOTE_PATTERN = 'imported via bulk uploader%'
LEGACY_SOURCE = 'legacy_decision_journal'
DEFAULT_SIGNAL = 'Default'
# The importer's made-up values on imported BUY decisions.
PLACEHOLDER_VALUES = (('confidence_score', 5), ('expected_return', 15), ('expected_timeframe', 60))

EXIT_CRITERIA_TO_JSON_USING = (
    "CASE WHEN exit_criteria IS NULL OR btrim(exit_criteria) = '' THEN NULL "
    "ELSE json_build_object('legacy_text', exit_criteria) END"
)

# Downgrade: a snapshot's rule texts, one per line, folded into legacy_text first,
# because ALTER ... USING can't hold a subquery. Then legacy_text becomes the text.
EXIT_CRITERIA_FOLD_RULES_SQL = r"""
    UPDATE decision_journal SET exit_criteria = json_build_object('legacy_text', (
        SELECT NULLIF(string_agg(r.value->>'text', E'\n' ORDER BY r.ordinality), '')
        FROM json_array_elements(exit_criteria->'rules') WITH ORDINALITY AS r))
    WHERE exit_criteria->>'legacy_text' IS NULL
      AND json_typeof(exit_criteria->'rules') = 'array'
"""
EXIT_CRITERIA_TO_TEXT_USING = "exit_criteria->>'legacy_text'"

journal_entry = sa.table(
    'journal_entry',
    sa.column('id', sa.Integer),
    sa.column('user_id', sa.Integer),
    sa.column('company_id', sa.Integer),
    sa.column('project_id', sa.Integer),
    sa.column('entry_type', sa.String),
    sa.column('title', sa.String),
    sa.column('content', sa.Text),
    sa.column('source', sa.String),
    sa.column('tags', sa.JSON),
    sa.column('is_archived', sa.Boolean),
    sa.column('is_starred', sa.Boolean),
    sa.column('review_count', sa.Integer),
    sa.column('created_at', sa.DateTime),
    sa.column('updated_at', sa.DateTime),
)


def repair_must_exit_companies(bind) -> int:
    """Give must-exit rules without a company their research project's company."""
    result = bind.execute(sa.text("""
        UPDATE journal_entry je SET company_id = rp.company_id
        FROM research_project rp
        WHERE rp.id = je.project_id AND rp.company_id IS NOT NULL
          AND je.entry_type = 'must_exit' AND je.company_id IS NULL
    """))
    return result.rowcount


def must_exit_ids_without_company(bind) -> list:
    return list(bind.execute(sa.text(
        "SELECT id FROM journal_entry WHERE entry_type = 'must_exit' AND company_id IS NULL ORDER BY id"
    )).scalars())


def require_must_exit_companies(bind) -> None:
    """Repair what can be repaired, then stop, naming the ids, if any must-exit
    rule still has no company. Never deletes them."""
    repair_must_exit_companies(bind)
    orphan_ids = must_exit_ids_without_company(bind)
    if orphan_ids:
        raise RuntimeError(
            'exit_plan_434: must-exit journal entries without a company (and none from their '
            f'research project); give them a company or delete them first: ids {orphan_ids}')


def _normalise(text_value: str) -> str:
    return ' '.join(text_value.split()).casefold()


def _clean_legacy_text(value: str) -> str:
    """BlockNote JSON becomes its plain text (one line per block); anything else is stripped."""
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        return blocknote_to_text(value, block_separator='\n').strip()
    return value.strip()


def move_legacy_rules(bind) -> int:
    """Copy each decision's legacy exit text into a must-exit rule for its company,
    once. Returns the number of rules created."""
    legacy_rows = bind.execute(sa.text("""
        SELECT user_id, company_id, exit_criteria->>'legacy_text' AS legacy_text
        FROM decision_journal
        WHERE exit_criteria->>'legacy_text' IS NOT NULL
        ORDER BY id
    """)).all()
    if not legacy_rows:
        return 0

    # Per (user, company): normalised texts of active rules and of every row
    # this migration made before (archived or not), so a rerun adds nothing.
    known = {}
    for user_id, company_id, content in bind.execute(sa.text("""
        SELECT user_id, company_id, content FROM journal_entry
        WHERE entry_type = 'must_exit' AND company_id IS NOT NULL
          AND (is_archived IS NOT TRUE OR source = :source)
    """), {'source': LEGACY_SOURCE}):
        known.setdefault((user_id, company_id), set()).add(_normalise(content or ''))

    projects = {}
    for user_id, company_id, project_id in bind.execute(sa.text(
            "SELECT user_id, company_id, min(id) FROM research_project "
            "WHERE company_id IS NOT NULL GROUP BY user_id, company_id")):
        projects[(user_id, company_id)] = project_id

    created = 0
    for user_id, company_id, legacy_text in legacy_rows:
        content = _clean_legacy_text(legacy_text)
        key = (user_id, company_id)
        if not content or _normalise(content) in known.get(key, set()):
            continue
        now = now_utc()
        bind.execute(journal_entry.insert().values(
            user_id=user_id,
            company_id=company_id,
            project_id=projects.get(key),
            entry_type='must_exit',
            title=DEFAULT_SIGNAL,
            content=content,
            source=LEGACY_SOURCE,
            tags=[],
            is_archived=False,
            is_starred=False,
            review_count=0,
            created_at=now,
            updated_at=now,
        ))
        known.setdefault(key, set()).add(_normalise(content))
        created += 1
    return created


def backfill_imported_transactions(bind) -> int:
    """Mark the bulk uploader's transactions, recognised by their note. The last
    time note text is used: the importer sets the column from now on."""
    result = bind.execute(sa.text(
        'UPDATE "transaction" SET is_imported = true '
        'WHERE is_imported = false AND notes ILIKE :pattern'
    ), {'pattern': IMPORTED_NOTE_PATTERN})
    return result.rowcount


def mark_imported_decisions(bind) -> None:
    """Mark imported decisions (the importer's BUY thesis, or a SELL linked to an
    imported transaction), then clear the importer's made-up values one field at a
    time, so a value the user changed stays. A BUY is never marked for its link alone:
    fix-imported-decisions links imported buys to the user's own opening decision."""
    bind.execute(sa.text("""
        UPDATE decision_journal SET is_imported = true
        WHERE is_imported = false
          AND (lower(btrim(investment_thesis)) = lower(:thesis)
               OR (decision_type = 'SELL'
                   AND id IN (SELECT decision_journal_id FROM "transaction"
                              WHERE is_imported AND decision_journal_id IS NOT NULL)))
    """), {'thesis': IMPORTED_BUY_THESIS})
    for column, placeholder in PLACEHOLDER_VALUES:
        bind.execute(sa.text(
            f"UPDATE decision_journal SET {column} = NULL "
            f"WHERE is_imported AND decision_type = 'BUY' AND {column} = :value"
        ), {'value': placeholder})


def upgrade():
    bind = op.get_bind()

    # 1. is_archived: no more NULLs.
    op.execute('UPDATE journal_entry SET is_archived = false WHERE is_archived IS NULL')
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.alter_column('is_archived', existing_type=sa.Boolean(), nullable=False,
                              server_default=sa.false())

    # 2. Must-exit rules need a company: repair from the project, stop on the rest.
    require_must_exit_companies(bind)

    # 3. The constraint and the coverage / buy-check index.
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.create_check_constraint('ck_journal_entry_must_exit_company',
                                         "entry_type <> 'must_exit' OR company_id IS NOT NULL")
        batch_op.create_index('ix_journal_entry_user_company_type',
                              ['user_id', 'company_id', 'entry_type'], unique=False)

    # 4. Top-ups and imported markers on decisions.
    with op.batch_alter_table('decision_journal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_decision_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_imported', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.create_foreign_key('fk_decision_journal_parent_decision_id', 'decision_journal',
                                    ['parent_decision_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('ix_decision_journal_parent_decision_id', ['parent_decision_id'],
                              unique=False)

    # 5. Imported marker on transactions, backfilled from the note once.
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_imported', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.create_index('ix_transaction_is_imported', ['is_imported'], unique=False)
    backfill_imported_transactions(bind)

    # 6. exit_criteria: free text becomes {"legacy_text": ...}.
    op.execute('ALTER TABLE decision_journal ALTER COLUMN exit_criteria TYPE json '
               f'USING {EXIT_CRITERIA_TO_JSON_USING}')

    # 7-8. Data: legacy text into must-exit rules; imported decisions marked.
    move_legacy_rules(bind)
    mark_imported_decisions(bind)


def downgrade():
    # exit_criteria back to text: legacy_text, else the snapshot's rule texts one per line, else NULL.
    op.execute(EXIT_CRITERIA_FOLD_RULES_SQL)
    op.execute('ALTER TABLE decision_journal ALTER COLUMN exit_criteria TYPE text '
               f'USING {EXIT_CRITERIA_TO_TEXT_USING}')

    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_index('ix_transaction_is_imported')
        batch_op.drop_column('is_imported')

    with op.batch_alter_table('decision_journal', schema=None) as batch_op:
        batch_op.drop_index('ix_decision_journal_parent_decision_id')
        batch_op.drop_constraint('fk_decision_journal_parent_decision_id', type_='foreignkey')
        batch_op.drop_column('is_imported')
        batch_op.drop_column('parent_decision_id')

    # Migrated rules and repaired company ids stay: they are valid data either way.
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.drop_index('ix_journal_entry_user_company_type')
        batch_op.drop_constraint('ck_journal_entry_must_exit_company', type_='check')
        batch_op.alter_column('is_archived', existing_type=sa.Boolean(), nullable=True,
                              server_default=None)
