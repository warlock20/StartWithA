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

"""Find a user's company by ticker, or create it. Shared by the importer and corporate actions."""

import logging

from app import db
from app.models.company import Company
from app.services.currency_service import CurrencyService
from app.services.financial_data import FinancialDataService

logger = logging.getLogger(__name__)


def get_or_create_company_by_ticker(user_id: int, ticker: str, financial_service=None) -> Company:
    """
    The user's company for this ticker (matched upper-case), created and flushed if missing.

    A new company takes its name and industry from the financial data service,
    falling back to "<TICKER> (Imported)" when the lookup fails.
    """
    ticker = ticker.upper().strip()
    existing = Company.query.filter(
        Company.user_id == user_id,
        db.func.upper(Company.ticker_symbol) == ticker
    ).first()
    if existing:
        return existing

    if financial_service is None:
        financial_service = FinancialDataService()

    company_name = None
    industry = None
    try:
        info = financial_service.get_ticker_info(ticker)
        if info:
            company_name = info.get('name')
            industry = info.get('industry')
            if company_name:
                logger.info(f"Fetched company info for {ticker}: {company_name}")
    except Exception as e:
        logger.warning(f"Could not fetch company info for {ticker}: {e}")

    if not company_name:
        company_name = f"{ticker} (Imported)"
        logger.info(f"Using fallback name for {ticker}")

    company = Company(
        name=company_name,
        ticker_symbol=ticker,
        user_id=user_id,
        is_in_portfolio=True,
        industry=industry,
        reporting_currency=CurrencyService.detect_currency_from_ticker(ticker)
    )
    db.session.add(company)
    db.session.flush()
    return company
