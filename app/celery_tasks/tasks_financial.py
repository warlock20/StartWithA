"""
Financial Data & SEC Filings Celery Tasks

Background tasks for fetching financial data, SEC filings, etc.
"""

import os
import shutil
import uuid
import re
import logging
import warnings
from datetime import timedelta
from pathlib import Path

import yfinance as yf
import pandas as pd
from secedgar import filings, FilingType
from weasyprint import HTML as WeasyHTML
from flask import current_app

from app import db, create_app
from app.models import Company, CompanyResource, User, FinancialData
from celery_app import celery
from app.utils.time_utils import now_utc, parse_date_to_date_object

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def fetch_financial_data_task(self, company_id):
    """
    A Celery task to fetch historical financial data for a company.
    """
    app = create_app()
    with app.app_context():
        company = Company.query.get(company_id)
        if not company or not company.creator:
            return f"Task failed: Company {company_id} or its creator not found."

        # Determine data depth based on user's subscription tier
        user = company.creator
        years_to_fetch = 5 if user.subscription_tier == 'free' else 15

        logger.info(f"TASK {self.request.id}: Fetching {years_to_fetch} years of financial data for {company.ticker_symbol}")

        try:
            ticker = yf.Ticker(company.ticker_symbol)

            # Define which metrics we want to extract
            metrics_to_get = {
                'income_statement': ['Total Revenue', 'Net Income'],
                'balance_sheet': ['Total Assets', 'Total Liab', 'Stockholders Equity'],
                'cash_flow': ['Free Cash Flow']
            }

            # Map to yfinance functions
            statement_map = {
                'income_statement': ticker.income_stmt,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow
            }

            saved_count = 0
            for statement_type, metrics in metrics_to_get.items():
                statement_df = statement_map[statement_type]
                if statement_df.empty:
                    continue

                # Limit to the number of years for the tier
                statement_df = statement_df.iloc[:, :years_to_fetch]

                for metric_name in metrics:
                    if metric_name in statement_df.index:
                        for period_date, value in statement_df.loc[metric_name].items():
                            # Check if this data point already exists
                            existing_data = FinancialData.query.filter_by(
                                company_id=company.id,
                                metric_name=metric_name,
                                period_date=period_date.date()
                            ).first()

                            if existing_data:
                                continue

                            new_data_point = FinancialData(
                                company_id=company.id,
                                statement_type=statement_type,
                                metric_name=metric_name,
                                period_date=period_date.date(),
                                value=int(value) if pd.notna(value) else 0
                            )
                            db.session.add(new_data_point)
                            saved_count += 1

            if saved_count > 0:
                db.session.commit()

            logger.info(f"TASK {self.request.id}: Saved {saved_count} data points")
            return f"Successfully saved {saved_count} new financial data points for {company.name}."

        except Exception as e:
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Failed - {e}")
            return f"Task failed: {e}"


@celery.task(bind=True, soft_time_limit=300, time_limit=360)
def fetch_sec_filings_task(self, company_id, user_id, years_to_fetch=5):
    """
    A Celery task to fetch SEC filings in the background.
    """
    app = create_app()
    with app.app_context():
        company = Company.query.get(company_id)
        user = User.query.get(user_id)
        if not company or not user:
            return "Task failed: Company or User not found."

        temp_download_path = Path(current_app.instance_path) / f"sec_temp_{self.request.id}"
        user_agent = f"{user.username} {user.email}"
        filing_type_str = '10-K'
        filing_type_enum = FilingType.FILING_10K

        try:
            logger.info(f"TASK {self.request.id}: Fetching {filing_type_str} filings for {company.ticker_symbol}")
            start_date = (now_utc() - timedelta(days=years_to_fetch * 365.25)).date()

            from bs4 import XMLParsedAsHTMLWarning
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

            filing_docs = filings(
                cik_lookup=company.ticker_symbol,
                filing_type=filing_type_enum,
                start_date=start_date,
                user_agent=user_agent
            )
            filing_docs.save(temp_download_path)

            company_filing_path = temp_download_path / company.ticker_symbol.upper() / filing_type_str
            saved_count = 0

            if company_filing_path.exists():
                for submission_file_path in company_filing_path.glob('*.txt'):
                    if not submission_file_path.is_file():
                        continue

                    logger.debug(f"Processing file: {submission_file_path.name}")

                    with open(submission_file_path, 'r', encoding='utf-8') as f:
                        full_filing_text = f.read()

                    # Parse filing date
                    filing_date_str = "N/A"
                    for line in full_filing_text.splitlines()[:40]:
                        if "FILED AS OF DATE:" in line:
                            date_val = line.split(":")[-1].strip()
                            filing_date_str = f"{date_val[0:4]}-{date_val[4:6]}-{date_val[6:8]}"
                            break

                    # Check for duplicates
                    doc_title = f"{filing_type_str} Report ({filing_date_str})"
                    existing_doc = CompanyResource.query.filter_by(
                        company_id=company.id,
                        title=doc_title,
                        resource_type='file'
                    ).first()
                    if existing_doc:
                        logger.debug(f"Skipping duplicate: {doc_title}")
                        continue

                    # Parse HTML content
                    doc_start_pattern = re.compile(r'<DOCUMENT>')
                    doc_end_pattern = re.compile(r'</DOCUMENT>')
                    doc_type_pattern = re.compile(r'<TYPE>' + re.escape(filing_type_str))
                    docs = list(zip(
                        [m.end() for m in doc_start_pattern.finditer(full_filing_text)],
                        [m.start() for m in doc_end_pattern.finditer(full_filing_text)]
                    ))

                    html_content = ''
                    for doc_start, doc_end in docs:
                        doc_text = full_filing_text[doc_start:doc_end]
                        if doc_type_pattern.search(doc_text):
                            text_start = re.search(r'<TEXT>', doc_text)
                            text_end = re.search(r'</TEXT>', doc_text)
                            if text_start and text_end:
                                html_content = doc_text[text_start.end():text_end.start()]
                                html_tag_start = html_content.find('<HTML>')
                                if html_tag_start != -1:
                                    html_content = html_content[html_tag_start:]
                                break

                    if not html_content:
                        logger.warning(f"Could not extract HTML from {submission_file_path.name}")
                        continue

                    # Convert HTML to PDF and save
                    original_fn = f"{company.ticker_symbol}_{filing_type_str}_{filing_date_str}.pdf"
                    stored_fn_uuid = f"{uuid.uuid4().hex}.pdf"
                    company_permanent_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(company.id))
                    os.makedirs(company_permanent_path, exist_ok=True)
                    file_save_path = os.path.join(company_permanent_path, stored_fn_uuid)

                    try:
                        WeasyHTML(string=html_content).write_pdf(file_save_path)
                    except Exception as pdf_err:
                        logger.warning(f"PDF conversion failed for {doc_title}, skipping: {pdf_err}")
                        continue

                    pdf_size = os.path.getsize(file_save_path)

                    new_doc = CompanyResource(
                        company_id=company.id,
                        user_id=user.id,
                        resource_type='file',
                        title=doc_title,
                        original_filename=original_fn,
                        stored_filename=os.path.join(str(company.id), stored_fn_uuid),
                        file_type='pdf',
                        file_size=pdf_size,
                        category=f"SEC {filing_type_str} Filings",
                        resource_date=parse_date_to_date_object(filing_date_str) if filing_date_str != "N/A" else None
                    )
                    db.session.add(new_doc)
                    saved_count += 1

            if saved_count > 0:
                db.session.commit()

            logger.info(f"TASK {self.request.id}: Processed {saved_count} filings")
            return f"Successfully processed {saved_count} new filings for {company.ticker_symbol}."

        except Exception as e:
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Failed - {e}")
            raise

        finally:
            if temp_download_path.exists():
                shutil.rmtree(temp_download_path)
