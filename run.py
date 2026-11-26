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

import os
import sys
import click
from whitenoise import WhiteNoise

from app import create_app, db
from celery_app import celery # Import the celery instance
from app.models import (User, Checklist, ChecklistItem, Company,
                        ChecklistAnalysis, ChecklistAnswer, CompanyResource,
                        Transaction, PortfolioPosition)
from app.services.portfolio_importer import PortfolioImporter
from app.services.financial_data import FinancialDataService
from app.services.feature_unlock_service import seed_unlock_thresholds
from app.services.outcome_tracking import backfill_received_outcomes, rebuild_trade_outcomes
from app.services.decision_journals import fix_imported_decisions
from app.services.expected_cagr_review import KINDS, convert_totals, keep_values, review_entries, set_values
from app.models.research import ResearchProject
from app.models.portfolio import backfill_holding_start_dates
# 1. Create the Flask app instance FIRST.
app = create_app()

# WhiteNoise: serve static files with gzip compression + cache headers
if not app.debug:
    app.wsgi_app = WhiteNoise(
        app.wsgi_app,
        root=os.path.join(app.static_folder),
        prefix='static/',
        max_age=31536000,  # 1 year cache
        immutable_file_test=lambda path, url: '/gen/' in url,
    )

# 2. NOW you can use the 'app' variable in decorators.
@app.shell_context_processor
def make_shell_context():
    """Makes additional variables available in the Flask shell context."""
    return {
        'app': app,
        'db': db,
        'User': User,
        'Checklist': Checklist,
        'ChecklistItem': ChecklistItem,
        'Company': Company,
        'ChecklistAnalysis': ChecklistAnalysis,
        'ChecklistAnswer': ChecklistAnswer,
        'CompanyResource': CompanyResource
    }

@app.cli.command("cleanup-legacy-tickers")
def cleanup_legacy_tickers_command():
    """Finds and reports legacy Google Finance format tickers (EXCHANGE:TICKER)."""
    with app.app_context():
        # Find all companies with ":" in ticker (Google Finance format)
        legacy_companies = Company.query.filter(
            Company.ticker_symbol.like('%:%')
        ).all()

        if not legacy_companies:
            print("No legacy tickers found. Database is clean!")
            return

        print(f"Found {len(legacy_companies)} legacy tickers (Google Finance format):\n")

        # Create a temporary importer to use its normalization function
        importer = PortfolioImporter.__new__(PortfolioImporter)

        for company in legacy_companies:
            old_ticker = company.ticker_symbol
            new_ticker = importer._normalize_ticker(old_ticker)

            # Check if normalized ticker already exists
            existing = Company.query.filter_by(
                user_id=company.user_id,
                ticker_symbol=new_ticker
            ).first()

            # Count transactions linked to this company
            txn_count = Transaction.query.filter_by(company_id=company.id).count()

            if existing:
                print(f"  ⚠️  {old_ticker} → {new_ticker} (DUPLICATE EXISTS: '{existing.name}')")
                print(f"      Legacy has {txn_count} transactions, duplicate has {Transaction.query.filter_by(company_id=existing.id).count()}")
            else:
                print(f"  🔄 {old_ticker} → {new_ticker} (can be converted)")
                print(f"      Has {txn_count} transactions")

        print(f"\n💡 To fix: Run 'flask fix-legacy-tickers' to convert/merge these.")


@app.cli.command("fix-legacy-tickers")
def fix_legacy_tickers_command():
    """Converts legacy Google Finance tickers to Yahoo format and merges duplicates.""" 
    with app.app_context():
        legacy_companies = Company.query.filter(
            Company.ticker_symbol.like('%:%')
        ).all()

        if not legacy_companies:
            print("No legacy tickers found.")
            return

        importer = PortfolioImporter.__new__(PortfolioImporter)
        converted = 0
        merged = 0

        for company in legacy_companies:
            old_ticker = company.ticker_symbol
            new_ticker = importer._normalize_ticker(old_ticker)

            # Check if normalized ticker already exists for this user
            existing = Company.query.filter_by(
                user_id=company.user_id,
                ticker_symbol=new_ticker
            ).first()

            if existing and existing.id != company.id:
                # MERGE: Move transactions to existing company, delete legacy
                print(f"  🔀 Merging {old_ticker} into {new_ticker} ('{existing.name}')")

                # Update transactions to point to existing company
                Transaction.query.filter_by(company_id=company.id).update(
                    {'company_id': existing.id}
                )

                # Delete legacy portfolio position if exists
                PortfolioPosition.query.filter_by(company_id=company.id).delete()

                # Delete legacy company
                db.session.delete(company)
                merged += 1
            else:
                # CONVERT: Just update the ticker symbol
                print(f"  ✅ Converting {old_ticker} → {new_ticker}")
                company.ticker_symbol = new_ticker
                converted += 1

        db.session.commit()
        print(f"\nDone! Converted: {converted}, Merged: {merged}")
        print("Run 'flask refresh-imported-companies' to fetch proper names.")


@app.cli.command("refresh-imported-companies")
def refresh_imported_companies_command():
    """Fetches real company names for all '(Imported)' companies."""
    with app.app_context():
        # Find all companies with "(Imported)" in the name
        imported_companies = Company.query.filter(
            Company.name.like('%(Imported)%')
        ).all()

        if not imported_companies:
            print("No imported companies found to refresh.")
            return

        print(f"Found {len(imported_companies)} imported companies to refresh...")

        service = FinancialDataService()
        updated = 0
        failed = 0

        for company in imported_companies:
            ticker = company.ticker_symbol
            if not ticker:
                print(f"  ⚠️  Skipping {company.name} - no ticker symbol")
                failed += 1
                continue

            try:
                info = service.get_ticker_info(ticker)
                if info and info.get('name'):
                    old_name = company.name
                    company.name = info['name']
                    if info.get('industry'):
                        company.industry = info['industry']
                    print(f"  ✅ {ticker}: '{old_name}' → '{company.name}'")
                    updated += 1
                else:
                    print(f"  ⚠️  {ticker}: No data found, keeping '{company.name}'")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {ticker}: Error - {e}")
                failed += 1

        db.session.commit()
        print(f"\nDone! Updated: {updated}, Failed: {failed}")


@app.cli.command("seed-unlock-thresholds")
def seed_unlock_thresholds_command():
    """Seeds default unlock thresholds for feature groups into SystemConfig."""
    with app.app_context():
        seed_unlock_thresholds()
        print("Feature unlock thresholds seeded.")


@app.cli.command("fix-imported-research-flags")
def fix_imported_research_flags_command():
    """Fixes bulk-imported BUY transactions that are missing the bought_without_research flag."""
    with app.app_context():
        imported_buys = Transaction.query.filter(
            Transaction.type == 'BUY',
            Transaction.notes.like('%Imported via Bulk Uploader%'),
            Transaction.bought_without_research == False
        ).all()

        if not imported_buys:
            print("No imported BUY transactions need fixing.")
            return

        fixed = 0
        for txn in imported_buys:
            research = ResearchProject.query.filter_by(
                company_id=txn.company_id,
                user_id=txn.user_id
            ).first()

            if not research:
                txn.bought_without_research = True
                fixed += 1
                print(f"  Fixed: {txn.company.ticker_symbol} ({txn.date}) - marked as without research")

        db.session.commit()
        print(f"\nDone! Fixed {fixed} out of {len(imported_buys)} imported BUY transactions.")


@app.cli.command("rebuild-trade-outcomes")
@click.option('--user-id', type=int, default=None, help='Only rebuild this user.')
@click.option('--dry-run', is_flag=True, help='Do the full rebuild, then roll back.')
def rebuild_trade_outcomes_command(user_id, dry_run):
    """Backfills realized_gain_loss_pct and per-trade ResearchOutcome rows, and re-links opening decisions."""
    with app.app_context():
        if dry_run:
            click.echo("DRY RUN — nothing written")
        reports = rebuild_trade_outcomes(user_id=user_id, dry_run=dry_run)
        totals = dict(companies=0, created=0, updated=0, deleted=0, closed=0, relinked=0,
                      positions_with_realized_pct=0)
        for r in reports:
            line = (f"user {r.user_id}: companies={r.companies} created={r.created} updated={r.updated} "
                    f"deleted={r.deleted} closed={r.closed} relinked={r.relinked} "
                    f"positions_with_realized_pct={r.positions_with_realized_pct}")
            if r.failed:
                line += f" FAILED: {r.error}"
            click.echo(line)
            for key in totals:
                totals[key] += getattr(r, key)
        failed = len([r for r in reports if r.failed])
        click.echo(f"TOTAL: users={len(reports)} " + " ".join(f"{k}={v}" for k, v in totals.items())
                   + f" failed={failed}")
        if dry_run:
            click.echo("DRY RUN — nothing written")
        if failed:
            sys.exit(1)


@app.cli.command("backfill-holding-start-dates")
@click.option('--user-id', type=int, default=None, help='Only backfill this user.')
@click.option('--dry-run', is_flag=True, help='Count the changes, then roll back.')
def backfill_holding_start_dates_command(user_id, dry_run):
    """Restarts days held at the re-buy for stocks sold out and bought back."""
    with app.app_context():
        if dry_run:
            click.echo("DRY RUN — nothing written")
        report = backfill_holding_start_dates(user_id=user_id, dry_run=dry_run)
        click.echo(f"positions checked={report['checked']} changed={report['changed']}")
        if dry_run:
            click.echo("DRY RUN — nothing written")


@app.cli.command("fix-imported-decisions")
@click.option('--user-id', type=int, default=None, help='Only fix this user.')
@click.option('--dry-run', is_flag=True, help='Do the full fix, then roll back.')
def fix_imported_decisions_command(user_id, dry_run):
    """Gives imported holding periods their missing opening decisions and links their later buys."""
    with app.app_context():
        if dry_run:
            click.echo("DRY RUN — nothing written")
        reports = fix_imported_decisions(user_id=user_id, dry_run=dry_run)
        totals = dict(companies=0, created=0, linked=0)
        for r in reports:
            line = f"user {r.user_id}: companies={r.companies} created={r.created} linked={r.linked}"
            if r.failed:
                line += f" FAILED: {r.error}"
            click.echo(line)
            for key in totals:
                totals[key] += getattr(r, key)
        failed = len([r for r in reports if r.failed])
        click.echo(f"TOTAL: users={len(reports)} " + " ".join(f"{k}={v}" for k, v in totals.items())
                   + f" failed={failed}")
        if dry_run:
            click.echo("DRY RUN — nothing written")
        if failed:
            sys.exit(1)


@app.cli.command("backfill-received-outcomes")
@click.option('--user-id', type=int, default=None, help='Only backfill this user.')
@click.option('--dry-run', is_flag=True, help='Do the full backfill, then roll back.')
def backfill_received_outcomes_command(user_id, dry_run):
    """Creates the missing is_received outcomes for holdings opened by a merger or spin-off (#451). Run once after deploy; safe to re-run."""
    with app.app_context():
        if dry_run:
            click.echo("DRY RUN — nothing written")
        reports = backfill_received_outcomes(user_id=user_id, dry_run=dry_run)
        totals = dict(companies=0, created=0, updated=0, deleted=0)
        for r in reports:
            line = (f"user {r.user_id}: companies={r.companies} created={r.created} "
                    f"updated={r.updated} deleted={r.deleted}")
            if r.failed:
                line += f" FAILED: {r.error}"
            click.echo(line)
            for key in totals:
                totals[key] += getattr(r, key)
        failed = len([r for r in reports if r.failed])
        click.echo(f"TOTAL: users={len(reports)} " + " ".join(f"{k}={v}" for k, v in totals.items())
                   + f" failed={failed}")
        if dry_run:
            click.echo("DRY RUN — nothing written")
        if failed:
            sys.exit(1)


@app.cli.group("expected-cagr")
def expected_cagr_group():
    """Review and fix expected CAGRs that may have been entered as a total return."""


def _parse_entry(text):
    kind, _, entry_id = text.partition(':')
    if kind not in KINDS or not entry_id.isdigit():
        raise click.BadParameter(f"{text!r}: use buy:<id> or thesis:<id>")
    return kind, int(entry_id)


def _echo_fix_results(results, dry_run):
    for r in results:
        if r.error:
            click.echo(f"{r.kind}:{r.id}  FAILED: {r.error}")
        else:
            click.echo(f"{r.kind}:{r.id}  {r.old} -> {r.new}")
    if any(r.error for r in results):
        click.echo("Nothing written: fix the failures and run again")
        sys.exit(1)
    click.echo("DRY RUN — nothing written" if dry_run else f"Saved {len(results)} entries")


@expected_cagr_group.command("review")
@click.option('--user-id', type=int, default=None, help='Only this user.')
def expected_cagr_review_command(user_id):
    """Lists expected returns saved before the CAGR change that may have been a total."""
    with app.app_context():
        entries = review_entries(user_id=user_id)
        click.echo("entry\tuser\tcompany\tentered\tvalue\ttimeframe_mo\tcagr_if_total\tsource")
        for e in entries:
            value = e.original_value if e.current_value == e.original_value else \
                f"{e.current_value} (was {e.original_value})"
            click.echo(f"{e.kind}:{e.id}\t{e.user_id}\t{e.company}\t{e.entered_on}\t{value}\t"
                       f"{e.timeframe_months}\t{e.cagr_if_total}\t{e.note}")
        click.echo(f"{len(entries)} entries to review. Resolve each with convert, set or keep.")


@expected_cagr_group.command("convert")
@click.argument('entries', nargs=-1, required=True)
@click.option('--dry-run', is_flag=True, help='Show the changes, then roll back.')
def expected_cagr_convert_command(entries, dry_run):
    """The value was a total over its timeframe: stores the CAGR it implies.

    ENTRIES are buy:<id> or thesis:<id>, as `review` prints them.
    """
    with app.app_context():
        _echo_fix_results(convert_totals([_parse_entry(e) for e in entries], dry_run=dry_run), dry_run)


@expected_cagr_group.command("set")
@click.argument('entry')
@click.argument('value', type=float)
@click.option('--dry-run', is_flag=True, help='Show the change, then roll back.')
def expected_cagr_set_command(entry, value, dry_run):
    """Sets one entry's expected CAGR (% a year), e.g. `set buy:12 15`."""
    with app.app_context():
        kind, entry_id = _parse_entry(entry)
        _echo_fix_results(set_values([(kind, entry_id, value)], dry_run=dry_run), dry_run)


@expected_cagr_group.command("keep")
@click.argument('entries', nargs=-1, required=True)
@click.option('--dry-run', is_flag=True, help='Show the changes, then roll back.')
def expected_cagr_keep_command(entries, dry_run):
    """The value was already a CAGR: leaves it and takes the entry off the list."""
    with app.app_context():
        _echo_fix_results(keep_values([_parse_entry(e) for e in entries], dry_run=dry_run), dry_run)


@app.cli.command("init-db")
def init_db_command():
    """Clears existing data and creates new tables."""
    # 1. Force enable the extension using a raw connection
    with app.app_context():
        from sqlalchemy import text
        try:
            # Use execution_options to ensure autocommit for extension creation
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("✅ pgvector extension enabled successfully.")
        except Exception as e:
            print(f"⚠️  Extension check failed: {e}")

        # 2. Now proceed with standard initialization
        db.drop_all()
        db.create_all()
        print("✅ Database initialized and tables created.")
        

# @app.cli.command("init-db")
# def init_db_command():
#     """Wipes database and creates new tables."""
#     with app.app_context():
#         # 1. Enable extension
#         try:
#             with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
#                 connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
#                 print("✅ pgvector extension enabled.")
#         except Exception as e:
#             print(f"⚠️ Extension check warning: {e}")

#         # 2. FORCE DROP ALL TABLES
#         # We manually drop tables with CASCADE to bypass the circular dependency error
#         try:
#             inspector = sqlalchemy.inspect(db.engine)
#             tables = inspector.get_table_names()
            
#             if tables:
#                 print(f"🗑️ Found {len(tables)} tables. Dropping with CASCADE...")
#                 with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
#                     for table in tables:
#                         # "CASCADE" forces deletion even if other tables link to it
#                         connection.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
#                 print("✅ All tables dropped.")
#             else:
#                 print("ℹ️ Database is already empty.")

#         except Exception as e:
#             print(f"⚠️ Error during drop: {e}")

#         # 3. Create Tables
#         print("🔨 Creating new tables...")
#         try:
#             db.create_all()
#             print("✅ Database initialized successfully!")
#         except Exception as e:
#             print(f"❌ Error creating tables: {e}")


@app.cli.command("reset-user")
def reset_user_command():
    """Reset a user account to factory state (preserves login credentials).

    Usage:  flask reset-user
    Prompts for the email address interactively.
    """
    import click
    from sqlalchemy import text
    from app.models import User

    email = click.prompt("Email of the user to reset")
    user = User.query.filter_by(email=email).first()
    if not user:
        print(f"No user found with email: {email}")
        return

    click.echo(f"This will DELETE all data for {user.email} (id={user.id}) "
               "and reset onboarding state.\nLogin credentials will be preserved.")
    if not click.confirm("Proceed?"):
        print("Aborted.")
        return

    uid = user.id

    # Tables split by how they reference the user:
    #   - tables_by_user_id: have a direct user_id column
    #   - tables_by_parent: no user_id, linked via a parent FK
    tables_by_user_id = [
        'ai_research_feedback',
        'prompt_usage_log',
        'bias_check_result',
        'ai_insight',
        'research_outcome',
        'embedding_store',
        'ml_prediction_log',
        'portfolio_ui_insights',
        'background_task',
        'pattern_recognition',
        'investment_postmortem',
        'learning_note',
        'thesis_evolution',
        'journal_template',
        'journal_entry',
        'decision_journal',
        'mistake_log',
        'free_research_question',
        'research_log',
        'research_metrics',
        'research_settings',
        'work_session',
        'template_step',
        'checklist_analysis',
        'research_project',
        'research_template',
        'kill_session',
        'kill_checklist_suggestion',
        'kill_checklist',
        'idea_source_analysis',
        'market_sweep_decision',
        'idea_pipeline',
        'transaction',
        'portfolio_position',
        'sector_analysis',
        'sector',
        'checklist',
        'question_bank_item',
        'destination_checkpoint',
        'document_imports',
        'document_annotation',
        'company_resource',
        'qualitative_analysis',
        'favorite_companies',
        'company',
        'user_investment_profile',
    ]

    # Child tables without user_id — delete via parent FK
    tables_by_parent = [
        # (table, fk_column, parent_table)
        ('kill_answer', 'kill_session_id', 'kill_session'),
        ('kill_criterion', 'kill_checklist_id', 'kill_checklist'),
        ('checklist_item', 'checklist_id', 'checklist'),
        ('checklist_answer', 'checklist_analysis_id', 'checklist_analysis'),
        ('journal_attachment', 'journal_entry_id', 'journal_entry'),
    ]

    conn = db.session.connection()
    # Disable trigger-based FK enforcement so delete order doesn't matter
    conn.execute(text('SET session_replication_role = replica'))

    try:
        # Delete child rows (no user_id) via their parent's user_id
        for table, fk_col, parent in tables_by_parent:
            conn.execute(text(
                f'DELETE FROM "{table}" WHERE "{fk_col}" IN '
                f'(SELECT id FROM "{parent}" WHERE user_id = :uid)'
            ), {'uid': uid})

        # Delete all tables that have a direct user_id column
        for table in tables_by_user_id:
            conn.execute(text(f'DELETE FROM "{table}" WHERE user_id = :uid'), {'uid': uid})

        # Reset user fields to factory defaults
        conn.execute(text('''
            UPDATE "user" SET
                onboarding_completed = false,
                onboarding_path_chosen = NULL,
                onboarding_completed_at = NULL,
                page_tours_completed = '{}',
                tour_preferences = '{"show_page_tours": true}',
                show_advanced_features = false,
                unlocked_features = '{}',
                newly_unlocked_features = '{}',
                ai_tokens_used = 0,
                ai_tokens_reset_date = NULL,
                ai_consent_given = false,
                ai_consent_date = NULL,
                cash_balance = 0,
                cash_setup_complete = false
            WHERE id = :uid
        '''), {'uid': uid})

        db.session.commit()
        print(f"User {email} has been reset to factory state.")
    except Exception as e:
        db.session.rollback()
        print(f"Reset failed: {e}")
    finally:
        # Restore normal FK enforcement
        try:
            conn.execute(text('SET session_replication_role = DEFAULT'))
        except Exception:
            pass


if __name__ == '__main__':
    app.run(debug=True)