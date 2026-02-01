import logging
from flask import request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (Company)
from app.services.sector_service import SectorService
from app.services.financial_data import FinancialDataService
from app.companies import companies_bp
from app.utils.ticker_validator import TickerValidator

logger = logging.getLogger(__name__)

# Module-level singleton for financial data lookups
_financial_service = None

def get_financial_service():
    """Lazy initialization of FinancialDataService singleton."""
    global _financial_service
    if _financial_service is None:
        _financial_service = FinancialDataService()
    return _financial_service

@companies_bp.route('/api/companies/search')
@login_required
def api_search_companies():
    """AJAX endpoint for searching companies - searches both user's companies and Yahoo Finance"""
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify({'user_companies': [], 'yahoo_suggestions': []})

    # Try to parse as ticker first
    normalized_ticker = None
    validation = TickerValidator.parse_and_validate(query)
    if validation['is_valid']:
        normalized_ticker = validation['normalized_ticker']

    # Search in user's existing companies by name and ticker
    # If we have a normalized ticker, search for that too
    search_conditions = [
        Company.name.ilike(f'%{query}%'),
        Company.ticker_symbol.ilike(f'%{query}%')
    ]

    if normalized_ticker and normalized_ticker != query.upper():
        # Also search for the normalized ticker
        search_conditions.append(Company.ticker_symbol.ilike(f'%{normalized_ticker}%'))

    user_companies = Company.query.filter(
        Company.user_id == current_user.id,
        db.or_(*search_conditions)
    ).order_by(Company.name).limit(10).all()

    user_company_data = []
    for company in user_companies:
        user_company_data.append({
            'id': company.id,
            'name': company.name,
            'ticker_symbol': company.ticker_symbol,
            'industry': company.industry,
            'sector': company.sector.display_name if company.sector else None,
            'source': 'existing'
        })

    # Try financial data service lookup - both by ticker AND by company name
    yahoo_suggestions = []
    service = get_financial_service()

    # 1. If query is a valid ticker, look it up directly
    if normalized_ticker:
        try:
            # Check if this ticker already exists for the user
            existing = Company.query.filter_by(
                ticker_symbol=normalized_ticker,
                user_id=current_user.id
            ).first()

            if not existing:
                info = service.get_ticker_info(normalized_ticker)

                if info and info.get('name'):
                    yahoo_suggestions.append({
                        'ticker_symbol': normalized_ticker,
                        'name': info.get('name'),
                        'industry': info.get('industry') or '',
                        'sector': info.get('sector') or '',
                        'summary': '',
                        'source': 'financial_data_service'
                    })
        except Exception:
            # Silently fail - expected for partial/invalid tickers during typing
            pass

    # 2. Search by company name (if not a ticker or no results from ticker search)
    if len(query) >= 3 and len(yahoo_suggestions) == 0:
        try:
            search_results = service.search_companies(query, max_results=5)

            for result in search_results[:3]:
                ticker_symbol = result.get('ticker_symbol')

                if not ticker_symbol:
                    continue

                # Skip if user already has this company
                existing = Company.query.filter_by(
                    ticker_symbol=ticker_symbol,
                    user_id=current_user.id
                ).first()

                if not existing:
                    yahoo_suggestions.append({
                        'ticker_symbol': ticker_symbol,
                        'name': result.get('name') or ticker_symbol,
                        'industry': result.get('industry') or '',
                        'sector': result.get('sector') or '',
                        'summary': '',
                        'source': 'financial_data_service'
                    })
        except Exception as e:
            logger.debug(f'Company search failed: {e}')
            pass

    return jsonify({
        'user_companies': user_company_data,
        'yahoo_suggestions': yahoo_suggestions
    })

@companies_bp.route('/api/companies/create', methods=['POST'])
@login_required
def api_create_company():
    """AJAX endpoint for creating new companies"""
    try:
        data = request.get_json()

        ticker_input = (data.get('ticker_symbol') or '').strip()
        name = (data.get('name') or '').strip()
        industry = (data.get('industry') or '').strip() or None
        sector_name = (data.get('sector') or '').strip() or None
        summary = (data.get('summary') or '').strip() or None

        # Validate ticker format
        validation = TickerValidator.parse_and_validate(ticker_input)

        if not validation['is_valid']:
            return jsonify({
                'success': False,
                'error': validation['errors'][0],
                'validation_errors': validation['errors'],
                'ticker_input': ticker_input
            })

        # Use normalized ticker (Yahoo Finance format)
        ticker_symbol = validation['normalized_ticker']

        if not name:
            return jsonify({'success': False, 'error': 'Company name is required'})

        # Check if company with same name or ticker already exists for this user
        existing = Company.query.filter(
            Company.user_id == current_user.id,
            db.or_(
                Company.name.ilike(name),
                Company.ticker_symbol == ticker_symbol
            )
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'error': 'Company with this name or ticker already exists'
            })

        # Find or create sector if provided
        sector_obj = None
        if sector_name:
            sector_obj = SectorService.find_or_create_sector(
                user_id=current_user.id,
                sector_name=sector_name,
                auto_create=True
            )

        # Create new company
        company = Company(
            user_id=current_user.id,
            name=name,
            ticker_symbol=ticker_symbol,
            industry=industry,
            sector_id=sector_obj.id if sector_obj else None,
            summary=summary
        )

        db.session.add(company)
        db.session.commit()

        return jsonify({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'ticker_symbol': company.ticker_symbol,
                'industry': company.industry,
                'sector': company.sector.display_name if company.sector else None,
                'summary': company.summary
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@companies_bp.route('/api/lookup/<ticker>')
@login_required
def api_lookup_ticker(ticker):
    """AJAX endpoint for looking up company info via FinancialDataService"""
    try:
        ticker_input = ticker.upper().strip()
        if not ticker_input:
            return jsonify({'success': False, 'error': 'Ticker symbol is required'})

        # Validate and normalize ticker
        validation = TickerValidator.parse_and_validate(ticker_input)
        if not validation['is_valid']:
            return jsonify({'success': False, 'error': validation['errors'][0]})

        # Use normalized ticker for lookup
        normalized_ticker = validation['normalized_ticker']

        # Try financial data service lookup
        service = get_financial_service()
        info = service.get_ticker_info(normalized_ticker)

        if info and info.get('name'):
            company_info = {
                'name': info.get('name'),
                'ticker_symbol': normalized_ticker,
                'summary': '',
                'sector': info.get('sector') or '',
                'industry': info.get('industry') or '',
                'source': 'financial_data_service',
                'exchange': validation['exchange_name']
            }

            return jsonify({
                'success': True,
                'company_info': company_info
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Could not find company data for ticker "{normalized_ticker}"'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error looking up ticker: {str(e)}'
        })            