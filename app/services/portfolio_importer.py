import os
import logging
import pandas as pd
from decimal import Decimal
from app import db
from app.models.user import User
from app.models.company import Company
from app.models.portfolio import Transaction, update_portfolio_position_for_company
from app.models.journal import DecisionJournal
from app.services.financial_data import FinancialDataService
from app.services.cash_service import CashService
from app.services.currency_service import CurrencyService

logger = logging.getLogger(__name__)

class PortfolioImportError(Exception):
    """Custom exception for import validation failures"""
    pass

class PortfolioImporter:
    def __init__(self, user_id):
        self.user = User.query.get(user_id)
        if not self.user:
            raise ValueError(f"User {user_id} not found")

        # Cache for company lookups to reduce DB hits
        # Format: {'TICKER': company_id}
        self.company_cache = {}
        self._load_company_cache()

        # Track companies that already have a BUY decision journal
        self.companies_with_buy_journal = self._load_existing_buy_journals()

        # User's base currency for conversion
        self.user_base_currency = self.user.base_currency

        # Reusable financial data service for company lookups
        self.financial_service = FinancialDataService()

    def _load_company_cache(self):
        companies = Company.query.filter_by(user_id=self.user.id).all()
        for c in companies:
            if c.ticker_symbol:  # Skip companies without ticker symbols
                self.company_cache[c.ticker_symbol.upper()] = c.id

    def _load_existing_buy_journals(self):
        """Load company IDs that already have a BUY decision journal."""
        existing = DecisionJournal.query.filter_by(
            user_id=self.user.id,
            decision_type='BUY',
            is_portfolio_decision=True
        ).with_entities(DecisionJournal.company_id).all()
        return {row.company_id for row in existing}

    def _get_or_create_company(self, ticker):
        ticker = ticker.upper().strip()
        if ticker in self.company_cache:
            return self.company_cache[ticker]

        # Try to fetch company info from financial data service
        company_name = None
        industry = None

        try:
            info = self.financial_service.get_ticker_info(ticker)
            if info:
                company_name = info.get('name')
                industry = info.get('industry')
                if company_name:
                    logger.info(f"Fetched company info for {ticker}: {company_name}")
        except Exception as e:
            logger.warning(f"Could not fetch company info for {ticker}: {e}")

        # Fallback to ticker if lookup failed
        if not company_name:
            company_name = f"{ticker} (Imported)"
            logger.info(f"Using fallback name for {ticker}")

        # Create new company
        new_company = Company(
            name=company_name,
            ticker_symbol=ticker,
            user_id=self.user.id,
            is_in_portfolio=True,
            industry=industry
        )
        db.session.add(new_company)
        db.session.flush()  # Flush to get the ID

        self.company_cache[ticker] = new_company.id
        return new_company.id
    
    def _detect_currency_from_ticker(self, ticker):
        """
        Detect currency from ticker suffix.
        Returns ISO 4217 currency code.
        """
        ticker = ticker.upper()

        # Suffix to currency mapping
        currency_map = {
            '.F': 'EUR',    # Frankfurt
            '.DE': 'EUR',   # Xetra (Germany)
            '.L': 'GBP',    # London
            '.HK': 'HKD',   # Hong Kong
            '.T': 'JPY',    # Tokyo
            '.TO': 'CAD',   # Toronto
            '.NS': 'INR',   # India NSE
            '.BO': 'INR',   # India BSE
            '.SS': 'CNY',   # Shanghai
            '.SZ': 'CNY',   # Shenzhen
            '.PA': 'EUR',   # Paris
            '.AS': 'EUR',   # Amsterdam
            '.BR': 'EUR',   # Brussels
            '.SW': 'CHF',   # SIX Swiss
            '.IS': 'TRY',   # Istanbul
            '.AX': 'AUD',   # Australia
            '.JO': 'ZAR',   # Johannesburg
        }

        # Check for suffix match
        for suffix, currency in currency_map.items():
            if ticker.endswith(suffix):
                return currency

        # Default to USD for US stocks or unknown
        return 'USD'

    def _normalize_ticker(self, raw_ticker):
        """
        Converts Google Finance format (EXCHANGE:TICKER) to Yahoo Finance (TICKER.SUFFIX).
        Example: FRA:1IG -> 1IG.F
        """
        raw_ticker = raw_ticker.upper().strip()

        # If no colon, assume it's already compatible or a US stock (e.g., AAPL, MSFT)
        if ':' not in raw_ticker:
            return raw_ticker

        exchange, ticker = raw_ticker.split(':', 1)
        
        # Mapping Google Finance Prefix -> Yahoo Finance Suffix
        # Add more as you discover them
        exchange_map = {
            'FRA': '.F',    # Frankfurt
            'ETR': '.DE',   # Xetra (Germany)
            'LON': '.L',    # London
            'HKG': '.HK',   # Hong Kong
            'TYO': '.T',    # Tokyo
            'TSE': '.TO',   # Toronto
            'NSE': '.NS',   # India NSE
            'BOM': '.BO',   # India BSE
            'SHA': '.SS',   # Shanghai
            'SHE': '.SZ',   # Shenzhen
            'EPA': '.PA',   # Paris
            'AMS': '.AS',   # Amsterdam
            'BRU': '.BR',   # Brussels
            'SWX': '.SW',   # SIX Swiss
            'IST': '.IS',   # Istanbul
            'ASX': '.AX',   # Australia
            'JSE': '.JO',   # Johannesburg
        }

        # Handle US Exchanges (Remove prefix, no suffix needed)
        us_exchanges = ['NASDAQ', 'NYSE', 'AMEX', 'ARCA']
        if exchange in us_exchanges:
            return ticker

        if exchange in exchange_map:
            return f"{ticker}{exchange_map[exchange]}"
        
        # Fallback: Return original if unknown (or log warning)
        print(f"⚠️ Warning: Unknown exchange mapping for {raw_ticker}")
        return raw_ticker

    def process_file(self, file_storage):
        """
        Accepts a Flask FileStorage object.
        """
        filename = file_storage.filename.lower()

        try:
            if filename.endswith('.csv'):
                file_storage.seek(0)
                df = pd.read_csv(file_storage)
            elif filename.endswith(('.xls', '.xlsx')):
                file_storage.seek(0)
                df = pd.read_excel(file_storage)
            else:
                raise PortfolioImportError("Unsupported file format. Use CSV or Excel.")
        except PortfolioImportError:
            raise
        except Exception as e:
            raise PortfolioImportError(f"Could not read file: {str(e)}")

        return self._process_dataframe(df)

    def process_file_from_path(self, file_path):
        """
        Process an import file from a disk path (for Celery background tasks).
        """
        filename = os.path.basename(file_path).lower()

        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file_path)
            else:
                raise PortfolioImportError("Unsupported file format. Use CSV or Excel.")
        except PortfolioImportError:
            raise
        except Exception as e:
            raise PortfolioImportError(f"Could not read file: {str(e)}")

        return self._process_dataframe(df)

    def _process_dataframe(self, df):
        """
        Shared logic for processing a DataFrame of transactions.
        """
        required_cols = [
            'Date', 'Type', 'Stock', 'Transacted Units', 'Transacted Price',
            'Fees', 'Previous Units', 'Cumulative Units'
        ]

        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise PortfolioImportError(f"Missing columns: {', '.join(missing)}")

        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date')

        created_transactions = []
        skipped_count = 0
        min_date = None
        max_date = None
        ticker_last_dates = {}

        try:
            for index, row in df.iterrows():
                try:
                    was_created = self._process_single_row(row, index)
                    ticker = self._normalize_ticker(str(row['Stock']).strip().upper())

                    if was_created:
                        created_transactions.append(ticker)

                        row_date = row['Date'].date()
                        if not min_date or row_date < min_date: min_date = row_date
                        if not max_date or row_date > max_date: max_date = row_date

                        if ticker not in ticker_last_dates or row_date > ticker_last_dates[ticker]:
                            ticker_last_dates[ticker] = row_date
                    else:
                        skipped_count += 1
                except Exception as e:
                    raise PortfolioImportError(f"Row {index + 2} Error: {str(e)}")

            db.session.commit()

            if created_transactions:
                self._update_affected_portfolios(set(created_transactions), ticker_last_dates)

            # Recalculate cash balance from all transactions
            CashService.recalculate_cash_balance(self.user.id)

            message_parts = []
            if created_transactions:
                message_parts.append(f"Imported {len(created_transactions)} transactions for {len(set(created_transactions))} companies")
            if skipped_count:
                message_parts.append(f"{skipped_count} duplicates skipped")
            if not created_transactions and skipped_count:
                message_parts.insert(0, "No new transactions")

            return {
                'count': len(created_transactions),
                'skipped': skipped_count,
                'companies': len(set(created_transactions)),
                'date_range': f"{min_date} to {max_date}" if min_date else "N/A",
                'message': '. '.join(message_parts) if message_parts else 'Import completed!'
            }

        except Exception as e:
            db.session.rollback()
            raise e
        
    def _process_single_row(self, row, row_index):
        # --- A. Extract Data ---
        txn_type_raw = str(row['Type']).strip().upper()
        raw_ticker = str(row['Stock']).strip().upper()
        ticker = self._normalize_ticker(raw_ticker)

        # Validate whole shares only
        units_raw = float(row['Transacted Units']) if pd.notna(row['Transacted Units']) else 0
        if units_raw != int(units_raw):
            raise ValueError(f"Fractional shares not supported. {ticker} has {units_raw} units (must be whole number)")
        units = int(units_raw)

        price = Decimal(str(row['Transacted Price'])) if pd.notna(row['Transacted Price']) else Decimal('0.00')
        fees = Decimal(str(row['Fees'])) if pd.notna(row['Fees']) else Decimal('0.00')
        split_ratio = Decimal(str(row['Stock Split Ratio'])) if 'Stock Split Ratio' in row and pd.notna(row['Stock Split Ratio']) else Decimal('1.0')

        # Validate whole shares for validation columns too
        prev_units_raw = float(row['Previous Units']) if pd.notna(row['Previous Units']) else 0
        cum_units_raw = float(row['Cumulative Units']) if pd.notna(row['Cumulative Units']) else 0
        if prev_units_raw != int(prev_units_raw) or cum_units_raw != int(cum_units_raw):
            raise ValueError(f"Fractional shares in Previous/Cumulative Units not supported for {ticker}")
        prev_units_check = int(prev_units_raw)
        cum_units_check = int(cum_units_raw)

        # --- B. Map Type to DB Enum ---
        # Input: Buy, Sell, Div, Stock split
        # DB: BUY, SELL, DIVIDEND, SPLIT
        type_map = {
            'BUY': 'BUY',
            'SELL': 'SELL',
            'DIV': 'DIVIDEND',
            'DIVIDEND': 'DIVIDEND',
            'STOCK SPLIT': 'SPLIT',
            'SPLIT': 'SPLIT'
        }
        
        if txn_type_raw not in type_map:
            raise ValueError(f"Unknown transaction type: {txn_type_raw}")
        
        db_type = type_map[txn_type_raw]

        # --- C. Validation (The "Cross Checking") ---
        # Logic:
        # BUY:  Prev + Units = Cumulative
        # SELL: Prev - Units = Cumulative
        # SPLIT: Prev * Ratio = Cumulative (Approximate, usually Split doesn't change unit count in this simplistic CSV, 
        #        BUT if the user log says "Stock Split", usually 'Transacted Units' is the NEW shares added?
        #        Let's stick to your prompt: "Cumulative Units -> Total units... after this transaction"
        
        calc_cumulative = 0
        if db_type == 'BUY':
            calc_cumulative = prev_units_check + units
        elif db_type == 'SELL':
            calc_cumulative = prev_units_check - units
        elif db_type == 'SPLIT':
            # For splits, usually the 'Transacted Units' isn't "added", 
            # usually the Row implies: We had X, now we have Y.
            # But let's follow the validation rule:
            # If the CSV implies specific math, check it.
            # Assuming for SPLIT, user puts 'Cumulative' as the new total.
            pass # Skipping rigid math check for split as formats vary wildly, trusting the user input for now.
        elif db_type == 'DIVIDEND':
            # Dividend doesn't change share count
            calc_cumulative = prev_units_check

        # Perform check (Skip for SPLIT to avoid complexity unless defined strict)
        if db_type in ['BUY', 'SELL', 'DIVIDEND'] and calc_cumulative != cum_units_check:
            raise ValueError(
                f"Validation Failed for {ticker}. "
                f"Previous ({prev_units_check}) +/- Transacted ({units}) != Cumulative ({cum_units_check}). "
                f"Calculated: {calc_cumulative}"
            )

        # --- D. Prepare DB Object ---
        company_id = self._get_or_create_company(ticker)

        # Handle specific field mapping based on Type
        db_price = price
        db_quantity = units

        if db_type == 'SPLIT':
            # Per your models.py logic, SPLIT stores the ratio in 'price_per_share'
            db_price = split_ratio
            # Quantity in DB for SPLIT usually implies the shares affected, or 0? 
            # calculate_fifo_cost_basis loops through ALL batches and multiplies by price_per_share.
            # It ignores 'quantity' on the split transaction row itself.
            db_quantity = 0 
        
        elif db_type == 'DIVIDEND':
            # Per your logic: dividend_amount = txn.quantity * txn.price_per_share
            # So Quantity = Shares Held, Price = Dividend Per Share
            # This matches standard inputs.
            pass

        # --- E. Duplicate Detection ---
        # Check if identical transaction already exists
        transaction_date = row['Date'].date()
        existing_txn = Transaction.query.filter_by(
            user_id=self.user.id,
            company_id=company_id,
            type=db_type,
            date=transaction_date,
            quantity=db_quantity,
            price_per_share=db_price
        ).first()

        if existing_txn:
            # Skip duplicate - log but don't raise error to allow partial imports
            print(f"⚠️ Skipping duplicate transaction: {ticker} {db_type} on {transaction_date} ({db_quantity} @ ${db_price})")
            return False  # Exit early, don't create duplicate

        # --- F. Detect Currency ---
        # Excel prices are in user's base currency by default, CSV 'Currency' column overrides
        if 'Currency' in row and pd.notna(row['Currency']):
            currency = str(row['Currency']).strip().upper()
        else:
            currency = self.user_base_currency

        # --- G. Currency Conversion to base ---
        exchange_rate = CurrencyService.get_exchange_rate(
            from_currency=currency,
            to_currency=self.user_base_currency,
            rate_date=transaction_date
        )
        price_per_share_base = db_price * exchange_rate
        fees_base = fees * exchange_rate

        txn = Transaction(
            user_id=self.user.id,
            company_id=company_id,
            type=db_type,
            date=transaction_date,
            quantity=db_quantity,
            price_per_share=db_price,
            fees=fees,
            price_per_share_base=price_per_share_base,
            fees_base=fees_base,
            exchange_rate=exchange_rate,
            exchange_rate_date=transaction_date,
            notes=f"Imported via Bulk Uploader. Row {row_index+2}",
            currency=currency
        )
        
        db.session.add(txn)
        db.session.flush()

        # Create Decision Journal entry for BUY (first purchase) and SELL
        self._create_import_decision_journal(
            company_id=company_id,
            transaction=txn,
            db_type=db_type,
            transaction_date=transaction_date
        )

        return True

    def _create_import_decision_journal(self, company_id, transaction, db_type, transaction_date):
        """Create a Decision Journal entry for imported transactions."""
        if db_type == 'BUY':
            if company_id in self.companies_with_buy_journal:
                return  # Already has a BUY journal (existing or from earlier row)

            journal = DecisionJournal(
                user_id=self.user.id,
                company_id=company_id,
                decision_type='BUY',
                decision_date=transaction_date,
                investment_thesis=f'Imported via bulk uploader',
                confidence_score=5,
                expected_return=15.0,
                expected_timeframe=60,
                is_portfolio_decision=True,
                thesis_depth='minimal',
                non_research_source='other'
            )
            db.session.add(journal)
            db.session.flush()
            transaction.decision_journal_id = journal.id
            self.companies_with_buy_journal.add(company_id)
            logger.info(f"Created BUY Decision Journal for company {company_id} (imported)")

        elif db_type == 'SELL':
            journal = DecisionJournal(
                user_id=self.user.id,
                company_id=company_id,
                decision_type='SELL',
                decision_date=transaction_date,
                investment_thesis=f'Selling {transaction.quantity} shares at ${transaction.price_per_share}',
                is_portfolio_decision=True
            )
            db.session.add(journal)
            db.session.flush()
            transaction.decision_journal_id = journal.id
            logger.info(f"Created SELL Decision Journal for company {company_id} (imported)")

    def _update_affected_portfolios(self, tickers, ticker_last_dates):
        """
        Recalculate portfolio positions for all tickers involved in the import.
        This is crucial for FIFO to work correctly.

        Args:
            tickers: Set of ticker symbols that were imported
            ticker_last_dates: Dict mapping ticker to last transaction date
        """
        print(f"Updating portfolios for: {tickers}")
        for ticker in tickers:
            if ticker not in self.company_cache:
                continue

            comp_id = self.company_cache[ticker]
            last_date = ticker_last_dates.get(ticker)

            # Use efficient update function that doesn't need to fetch a transaction
            # It only needs company_id and user_id, and we already have those
            update_portfolio_position_for_company(
                company_id=comp_id,
                user_id=self.user.id,
                last_transaction_date=last_date
            )
            print(f"✓ Updated portfolio for {ticker}")

        db.session.commit()