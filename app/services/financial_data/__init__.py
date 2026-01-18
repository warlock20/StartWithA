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
