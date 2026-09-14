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

import logging
from flask import request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (Company)
from app.models.market_sweep import (
    CompanySweepLink, MarketSweep, MarketSweepCompany,
)
from app.models.research import FreeResearchQuestion
from app.services.sector_service import SectorService
from app.services.financial_data import FinancialDataService
from app.companies import companies_bp
from app.utils.ticker_validator import TickerValidator
from app.utils.company_identity import company_identity_key, normalize_company_name
from app.utils.isin import is_valid_isin, isin_plausible_for_listing, normalize_isin
from app.services.currency_service import CurrencyService
from app.services.sweep_link import confirm as confirm_link, link_from_isin
from app.utils.response_utils import json_error, json_not_found
from app.utils.time_utils import now_utc
from app.utils.blocknote_utils import append_note, blocknote_to_text

logger = logging.getLogger(__name__)

# Module-level singleton for financial data lookups
_financial_service = None

def get_financial_service():
    """Lazy initialization of FinancialDataService singleton."""
    global _financial_service
    if _financial_service is None:
        _financial_service = FinancialDataService()
    return _financial_service

def _serialize_user_company(company):
    """Shape a Company the user owns for the search response."""
    return {
        'id': company.id,
        'name': company.name,
        'ticker_symbol': company.ticker_symbol,
        'industry': company.industry,
        'sector': company.sector.display_name if company.sector else None,
        'isin': company.isin,
        'source': 'existing'
    }


def _trusted_provider_isin(raw, ticker):
    """A provider's ISIN, or None if it fails either check.

    Two gates, both cheap and both necessary. is_valid_isin catches a mangled
    string; isin_plausible_for_listing catches a well-formed ISIN belonging to
    something else, which is the failure a check digit cannot see.

    Applied on the way out of search AND again on the way into create. The
    second is not redundant: the first ran on data the client then had a turn
    with, and an ISIN accepted here is written as fact.
    """
    isin = normalize_isin(raw)
    if not isin or not is_valid_isin(isin):
        return None
    if not isin_plausible_for_listing(isin, ticker):
        logger.info(
            'Discarded provider ISIN %s for %s: country prefix contradicts '
            'the listing.', isin, ticker)
        return None
    return isin


def _serialize_sweep_row(row, sweep):
    """Shape a market-sweep row for the search response."""
    return {
        'sweep_company_id': row.id,
        'company_name': row.company_name,
        'ticker': row.ticker,
        'isin': row.isin,
        'sector_label': row.sector_label,
        'exchange': row.exchange,
        'sweep_name': sweep.name,
        'sweep_country': sweep.country,
        'source': 'market_sweep',
    }


@companies_bp.route('/api/companies/search')
@login_required
def api_search_companies():
    """AJAX endpoint for searching companies - searches both user's companies and Yahoo Finance"""
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify({'user_companies': [], 'sweep_companies': [],
                        'yahoo_suggestions': []})

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

    user_company_data = [_serialize_user_company(c) for c in user_companies]
    listed_company_ids = {c['id'] for c in user_company_data}

    # Identity of every company the user already owns. The ticker saved on the
    # company is the user's own choice of exchange, so a provider listing of the
    # same company under any other ticker is a duplicate, not a new company.
    owned_rows = db.session.query(
        Company.id, Company.name, Company.ticker_symbol
    ).filter(Company.user_id == current_user.id).all()

    owned_company_ids = {}
    for company_id, name, ticker in owned_rows:
        owned_company_ids.setdefault(company_identity_key(name, ticker), company_id)

    def claim_owned_company(identity):
        """
        Resolve a provider listing against the user's own companies.

        Returns True when the company is already owned, in which case it is
        surfaced under the user's saved ticker rather than offered again. A
        user who saved Microsoft as MSF.F and then searches "MSFT" must still
        see their own holding, otherwise the UI offers to create a duplicate.
        """
        company_id = owned_company_ids.get(identity)
        if company_id is None:
            return False

        if company_id not in listed_company_ids:
            listed_company_ids.add(company_id)
            user_company_data.append(
                _serialize_user_company(db.session.get(Company, company_id))
            )
        return True

    # Market-sweep rows. These are the only records in the system carrying a
    # human-entered ISIN, so they are searched before the provider and rank
    # above it: a provider listing of the same company is the same company
    # minus its identifier.
    sweep_companies = []
    sweep_identities = set()

    linked_row_ids = {
        row_id for (row_id,) in db.session.query(
            CompanySweepLink.sweep_company_id
        ).filter(CompanySweepLink.user_id == current_user.id).all()
    }

    sweep_rows = db.session.query(MarketSweepCompany, MarketSweep).join(
        MarketSweep, MarketSweep.id == MarketSweepCompany.sweep_id
    ).filter(
        MarketSweep.is_active.is_(True),
        db.or_(
            MarketSweepCompany.company_name.ilike(f'%{query}%'),
            MarketSweepCompany.ticker.ilike(f'%{query}%'),
        )
    ).order_by(MarketSweepCompany.company_name).limit(20).all()

    for row, sweep in sweep_rows:
        identity = company_identity_key(row.company_name, row.ticker)

        # A row this user has already answered for -- by linking it, or by
        # simply owning the company -- is settled. Offering it again is an
        # invitation to create the duplicate this endpoint exists to prevent.
        # The ISIN still reaches an owned-but-unlinked company, through the
        # sweep-match banner rather than through a second creation.
        if row.id in linked_row_ids or claim_owned_company(identity):
            continue

        if identity in sweep_identities:
            continue
        sweep_identities.add(identity)
        sweep_companies.append(_serialize_sweep_row(row, sweep))
        if len(sweep_companies) >= 5:
            break

    # Try financial data service lookup - both by ticker AND by company name
    yahoo_suggestions = []
    # Seeded with the sweep hits so the provider cannot re-offer a company the
    # sweep already answered for, without its ISIN.
    suggested_identities = set(sweep_identities)
    service = get_financial_service()

    # 1. If query is a valid ticker, look it up directly
    if normalized_ticker:
        try:
            info = service.get_ticker_info(normalized_ticker)

            if info and info.get('name'):
                identity = company_identity_key(info.get('name'), normalized_ticker)

                # Skip if the user already owns this company, under any
                # ticker, or a sweep row already covers it
                if (identity not in suggested_identities
                        and not claim_owned_company(identity)):
                    suggested_identities.add(identity)
                    yahoo_suggestions.append({
                        'ticker_symbol': normalized_ticker,
                        'name': info.get('name'),
                        'industry': info.get('industry') or '',
                        'sector': info.get('sector') or '',
                        'summary': '',
                        # Optional in the provider contract; Yahoo never sets
                        # it. See _trusted_provider_isin.
                        'isin': _trusted_provider_isin(
                            info.get('isin'), normalized_ticker),
                        'source': 'financial_data_service'
                    })
        except Exception:
            # Silently fail - expected for partial/invalid tickers during typing
            pass

    # 2. Search by company name (if not a ticker or no results from ticker search)
    if len(query) >= 3 and len(yahoo_suggestions) == 0:
        try:
            # The service already collapses cross-listings to one row per company
            search_results = service.search_companies(query, max_results=3)

            for result in search_results:
                ticker_symbol = result.get('ticker_symbol')
                name = result.get('name') or ticker_symbol

                identity = company_identity_key(name, ticker_symbol)
                if identity in suggested_identities or claim_owned_company(identity):
                    continue

                suggested_identities.add(identity)
                yahoo_suggestions.append({
                    'ticker_symbol': ticker_symbol,
                    'name': name,
                    'industry': result.get('industry') or '',
                    'sector': result.get('sector') or '',
                    'summary': '',
                    'isin': _trusted_provider_isin(
                        result.get('isin'), ticker_symbol),
                    'source': 'financial_data_service'
                })
        except Exception as e:
            logger.debug(f'Company search failed: {e}')
            pass

    return jsonify({
        'user_companies': user_company_data,
        'sweep_companies': sweep_companies,
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
        sweep_company_id = data.get('sweep_company_id')

        # The row the user picked, when they picked one. Its ISIN is the
        # reason this branch exists: it is the only identifier in the system a
        # human has actually vouched for.
        sweep_company = None
        if sweep_company_id is not None:
            sweep_company = MarketSweepCompany.query.get(sweep_company_id)
            if sweep_company is None:
                return json_error('That market sweep company no longer exists')
            if not ticker_input:
                ticker_input = (sweep_company.ticker or '').strip()

        # A sweep row with no ticker is still a real company, and the sweep's
        # own promote path has always recorded it as UNKNOWN. Refusing it here
        # would make the row unusable through the modal alone.
        if sweep_company is not None and not ticker_input:
            ticker_symbol = 'UNKNOWN'
        else:
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
            return json_error('Company name is required')

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

        # The row's ISIN travels with the company, but only if it is free:
        # uq_company_user_isin allows a user one company per ISIN, and silently
        # dropping it here would leave the user staring at a company that
        # refuses to link to the row they just picked.
        # A sweep ISIN was typed by a person and outranks anything a provider
        # proposed; the provider's is re-checked here because the client had a
        # turn with it in between.
        isin = sweep_company.isin if sweep_company is not None else None
        if isin is None:
            isin = _trusted_provider_isin(data.get('provider_isin'), ticker_symbol)
        if isin:
            clash = Company.query.filter(
                Company.user_id == current_user.id,
                Company.isin == isin,
            ).first()
            if clash is not None:
                return jsonify({
                    'success': False,
                    'error': (
                        f'ISIN {isin} is already assigned to {clash.name}. '
                        f'Link that company to this row instead.'
                    ),
                })

        # Create new company
        company = Company(
            user_id=current_user.id,
            name=name,
            ticker_symbol=ticker_symbol,
            industry=industry,
            sector_id=sector_obj.id if sector_obj else None,
            summary=summary,
            isin=isin,
            reporting_currency=CurrencyService.detect_currency_from_ticker(ticker_symbol)
        )

        db.session.add(company)
        db.session.flush()

        if sweep_company is not None:
            # Choosing the row is the judgement, so the link is 'confirmed'.
            # link_from_isin then carries the same answer to every other row
            # bearing this ISIN, where no judgement was made and the origin
            # says so.
            confirm_link(current_user.id, sweep_company.id, company.id)
            if isin:
                link_from_isin(current_user.id, isin)

        db.session.commit()

        return jsonify({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'ticker_symbol': company.ticker_symbol,
                'industry': company.industry,
                'sector': company.sector.display_name if company.sector else None,
                'summary': company.summary,
                'isin': company.isin
            }
        })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e))


def _owned_company_or_404(company_id):
    """This user's company, or None. Another user's is indistinguishable from
    one that does not exist, which is the point."""
    return Company.query.filter_by(
        id=company_id, user_id=current_user.id).first()


def _sweep_match_candidates(company):
    """Sweep rows whose ISIN this company might be entitled to.

    Exact ticker first, then normalised name -- the same ladder sweep_link.
    suggest() climbs, and for the same reason: a name is a guess, so it ranks
    below an identifier and never writes anything on its own.

    A row whose ISIN the user already holds elsewhere is omitted. Offering it
    would propose a change that uq_company_user_isin then refuses, which reads
    to the user as the app being broken rather than as a real conflict.
    """
    if company.isin:
        return []

    held = {
        isin for (isin,) in db.session.query(Company.isin).filter(
            Company.user_id == current_user.id,
            Company.isin.isnot(None),
            Company.id != company.id,
        ).all()
    }

    rows = db.session.query(MarketSweepCompany, MarketSweep).join(
        MarketSweep, MarketSweep.id == MarketSweepCompany.sweep_id
    ).filter(
        MarketSweep.is_active.is_(True),
        MarketSweepCompany.isin.isnot(None),
    ).all()

    normalized = normalize_company_name(company.name)
    by_ticker, by_name = [], []

    for row, sweep in rows:
        if row.isin in held:
            continue
        if company.ticker_symbol and row.ticker == company.ticker_symbol:
            target = by_ticker
            basis = 'ticker'
        elif normalized and normalize_company_name(row.company_name) == normalized:
            target = by_name
            basis = 'name'
        else:
            continue
        hit = _serialize_sweep_row(row, sweep)
        hit['basis'] = basis
        target.append(hit)

    return by_ticker + by_name


@companies_bp.route('/api/companies/<int:company_id>/sweep-match')
@login_required
def api_company_sweep_match(company_id):
    """Sweep rows carrying an ISIN that this ISIN-less company might be.

    Read-only by design. The banner this feeds is the human gate: an ISIN
    written here would travel to every user holding it, as a link claiming no
    judgement was required.
    """
    company = _owned_company_or_404(company_id)
    if company is None:
        return json_not_found('Company not found')

    return jsonify({
        'success': True,
        'matches': _sweep_match_candidates(company),
    })


@companies_bp.route('/api/companies/<int:company_id>/adopt-isin', methods=['POST'])
@login_required
def api_company_adopt_isin(company_id):
    """Take the ISIN from a sweep row the user has just accepted.

    The click is the judgement, so the link is stamped 'confirmed' exactly as
    it is when the row is picked during creation.
    """
    company = _owned_company_or_404(company_id)
    if company is None:
        return json_not_found('Company not found')

    sweep_company_id = (request.get_json() or {}).get('sweep_company_id')
    sweep_company = MarketSweepCompany.query.get(sweep_company_id) \
        if sweep_company_id is not None else None
    if sweep_company is None:
        return json_error('That market sweep company no longer exists')

    if not sweep_company.isin:
        return json_error('That market sweep row has no ISIN to take')

    clash = Company.query.filter(
        Company.user_id == current_user.id,
        Company.isin == sweep_company.isin,
        Company.id != company.id,
    ).first()
    if clash is not None:
        return json_error(
            f'ISIN {sweep_company.isin} is already assigned to {clash.name}.')

    try:
        company.isin = sweep_company.isin
        confirm_link(current_user.id, sweep_company.id, company.id)
        link_from_isin(current_user.id, company.isin)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception('Adopting ISIN from sweep row failed')
        return json_error(str(exc))

    return jsonify({
        'success': True,
        'company': {'id': company.id, 'isin': company.isin},
    })


@companies_bp.route('/api/lookup/<ticker>')
@login_required
def api_lookup_ticker(ticker):
    """AJAX endpoint for looking up company info via FinancialDataService"""
    try:
        ticker_input = ticker.upper().strip()
        if not ticker_input:
            return json_error('Ticker symbol is required')

        # Validate and normalize ticker
        validation = TickerValidator.parse_and_validate(ticker_input)
        if not validation['is_valid']:
            return json_error(validation['errors'][0])

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


@companies_bp.route('/api/<int:company_id>/journey-notes', methods=['GET'])
@login_required
def get_journey_notes(company_id):
    """Get BlockNote journey notes for a company."""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_not_found('Company not found')

    return jsonify({
        'success': True,
        'content': company.journey_notes or ''
    })


@companies_bp.route('/api/<int:company_id>/journey-notes', methods=['POST'])
@login_required
def save_journey_notes(company_id):
    """Save BlockNote journey notes for a company."""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_not_found('Company not found')

    data = request.get_json()
    if not data or 'content' not in data:
        return json_error('No content provided')

    company.journey_notes = data['content']
    company.journey_notes_updated_at = now_utc()
    db.session.commit()

    return jsonify({'success': True})


@companies_bp.route('/api/<int:company_id>/journey-notes/append', methods=['POST'])
@login_required
def append_journey_note(company_id):
    """Append a dated note to a company's notes without loading the editor.

    Used by the quick Add Note button on the research project page. The heading
    names the project when one is given, so you can tell which research session
    produced the note.
    """
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_not_found('Company not found')

    data = request.get_json() or {}
    note = data.get('content') or data.get('text') or ''
    # The editor always sends a document, so emptiness is about the text inside
    # it, not the string being blank.
    if not blocknote_to_text(note).strip():
        return json_error('Note text is required')

    heading = now_utc().strftime('%d %b %Y').lstrip('0')
    project_name = (data.get('project_name') or '').strip()
    if project_name:
        heading = f'{heading} — {project_name}'

    company.journey_notes = append_note(company.journey_notes, note, heading)
    company.journey_notes_updated_at = now_utc()
    db.session.commit()

    return jsonify({'success': True})


# ===================================================================
#  Standalone Research Questions API (list + create only;
#  PUT/DELETE reuse existing /research/workflow/api/questions/<id>)
# ===================================================================

@companies_bp.route('/api/<int:company_id>/research-questions')
@login_required
def api_list_research_questions(company_id):
    """List standalone (non-project) research questions for a company."""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_not_found('Company')

    questions = FreeResearchQuestion.query.filter_by(
        company_id=company_id,
        user_id=current_user.id,
        project_id=None
    ).order_by(FreeResearchQuestion.order_index).all()

    return jsonify({
        'success': True,
        'questions': [{
            'id': q.id,
            'question_text': q.question_text,
            'answer_content': q.answer_content,
            'status': q.status,
            'order_index': q.order_index,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'updated_at': q.updated_at.isoformat() if q.updated_at else None,
            'answered_at': q.answered_at.isoformat() if q.answered_at else None,
        } for q in questions]
    })


@companies_bp.route('/api/<int:company_id>/research-questions', methods=['POST'])
@login_required
def api_create_research_question(company_id):
    """Create a new standalone research question for a company."""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_not_found('Company')

    data = request.get_json()
    if not data or not data.get('question_text', '').strip():
        return json_error('Question text is required')

    max_order = db.session.query(db.func.max(FreeResearchQuestion.order_index)).filter_by(
        company_id=company_id,
        user_id=current_user.id,
        project_id=None
    ).scalar() or -1

    question = FreeResearchQuestion(
        user_id=current_user.id,
        company_id=company_id,
        project_id=None,
        step_index=None,
        question_text=data['question_text'].strip(),
        status='exploring',
        order_index=max_order + 1
    )

    db.session.add(question)
    db.session.commit()

    return jsonify({
        'success': True,
        'question': {
            'id': question.id,
            'question_text': question.question_text,
            'answer_content': question.answer_content,
            'status': question.status,
            'order_index': question.order_index,
            'created_at': question.created_at.isoformat(),
        }
    })