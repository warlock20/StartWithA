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
from whitenoise import WhiteNoise

from app import create_app, db
from celery_app import celery # Import the celery instance
from app.models import (User, Checklist, ChecklistItem, Company,
                        ChecklistAnalysis, ChecklistAnswer, CompanyResource,
                        Transaction, PortfolioPosition)
from app.services.portfolio_importer import PortfolioImporter
from app.services.financial_data import FinancialDataService
from app.services.feature_unlock_service import seed_unlock_thresholds
from app.models.research import ResearchProject
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