# Investment Checklist Platform
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

"""
Financial Data Service

Provider-agnostic financial data service for fetching stock prices and company info.

Usage:
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()

    # Current price
    price = service.get_current_price('AAPL')

    # Historical price
    from datetime import date
    price = service.get_historical_price('AAPL', date(2024, 1, 31))

    # Bulk historical prices
    prices = service.get_historical_prices_bulk('AAPL', date(2024, 1, 1), date(2024, 12, 31))
"""

from .financial_data_service import FinancialDataService
from .providers import (
    FinancialDataProvider,
    YahooFinanceProvider,
    CachedFinancialDataProvider
)

__all__ = [
    'FinancialDataService',
    'FinancialDataProvider',
    'YahooFinanceProvider',
    'CachedFinancialDataProvider',
]
