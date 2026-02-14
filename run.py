from app import create_app, db
from celery_app import celery # Import the celery instance
from app.models import (User, Checklist, ChecklistItem, Company,
                        ChecklistAnalysis, ChecklistAnswer, CompanyDocument,
                        Transaction, PortfolioPosition)
from sqlalchemy import text
from app.services.portfolio_importer import PortfolioImporter
from app.services.financial_data import FinancialDataService
# 1. Create the Flask app instance FIRST.
app = create_app()

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
        'CompanyDocument': CompanyDocument
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


if __name__ == '__main__':
    app.run(debug=True)