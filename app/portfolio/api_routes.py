'''
API routes for portfolio-related AJAX calls.
'''
import logging
from flask import request, jsonify
from flask_login import login_required, current_user
from app.services.intelligence_engine import IntelligenceEngine

from app.portfolio import portfolio_bp
from app.models import Company
from app import db, limiter
from app.constants import RATELIMIT_AI

from app.services.intelligence_engine import check_sell_warnings
from app.services.thesis_analysis import get_quick_thesis_assessment, analyze_thesis
from app.services.similar_mistakes import find_similar_past_decisions

logger = logging.getLogger(__name__)

@portfolio_bp.route('/api/company-search')
@login_required
def company_search():
    """API endpoint for company autocomplete search"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify([])

    companies = Company.query.filter(
        Company.user_id == current_user.id,
        db.or_(
            Company.name.ilike(f'%{query}%'),
            Company.ticker_symbol.ilike(f'%{query}%')
        )
    ).order_by(Company.name).limit(10).all()

    results = [{
        'id': c.id,
        'name': c.name,
        'ticker': c.ticker_symbol,
        'label': f'{c.ticker_symbol} - {c.name}'
    } for c in companies]

    return jsonify(results)

@portfolio_bp.route('/api/check-warnings', methods=['POST'])
@login_required
def check_transaction_warnings():
    """
    API endpoint to check warnings before transaction.
    Called via AJAX as user fills out the form.
    
    Request JSON:
        {
            "company_id": 123,
            "transaction_type": "BUY",
            "quantity": 100,
            "price_per_share": 150.00
        }
    
    Response JSON:
        {
            "warnings": [...],
            "count": 3,
            "has_high_severity": true
        }
    """    
    data = request.get_json()
    
    if not data:
        return jsonify({'warnings': [], 'count': 0, 'has_high_severity': False})
    
    company_id = data.get('company_id')
    transaction_type = data.get('transaction_type')
    quantity = data.get('quantity')
    price_per_share = data.get('price_per_share')
    
    warnings = []
    
    # Only check warnings for BUY transactions
    if transaction_type == 'BUY' and company_id and quantity and price_per_share:
        try:
            amount = float(quantity) * float(price_per_share)
            engine = IntelligenceEngine(current_user.id)
            warnings = engine.check_buy_transaction(int(company_id), amount)
        except (ValueError, TypeError) as e:
            # Invalid input, return no warnings
            pass
    
    # Convert warnings to JSON-serializable format
    warnings_data = [
        {
            'code': w.code,
            'severity': w.severity,
            'category': w.category,
            'title': w.title,
            'message': w.message,
            'data': w.data,
            'action_url': w.action_url,
            'dismissible': w.dismissible
        }
        for w in warnings
    ]
    
    has_high = any(w['severity'] == 'high' for w in warnings_data)
    
    return jsonify({
        'warnings': warnings_data,
        'count': len(warnings_data),
        'has_high_severity': has_high
    })
    
@portfolio_bp.route('/api/check-sell-warnings', methods=['POST'])
@login_required
def check_sell_transaction_warnings():
    """API endpoint to check warnings before SELL transaction."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'warnings': [], 'count': 0, 'error': None})
        
        company_id = data.get('company_id')
        shares = data.get('shares')
        
        # Input validation
        if not company_id or not shares:
            return jsonify({'warnings': [], 'count': 0, 'error': None})
        
        try:
            company_id = int(company_id)
            shares = int(shares)
            if shares <= 0:
                return jsonify({'warnings': [], 'count': 0, 'error': 'Invalid share count'})
        except (ValueError, TypeError):
            return jsonify({'warnings': [], 'count': 0, 'error': 'Invalid input'})
        
        warnings = check_sell_warnings(current_user.id, company_id, shares)
        
        return jsonify({
            'warnings': [w.to_dict() for w in warnings],
            'count': len(warnings),
            'has_high_severity': any(w.severity == 'high' for w in warnings),
            'error': None
        })
        
    except Exception as e:
        logger.error(f"Error checking sell warnings: {e}")
        # Return empty warnings - don't block the transaction
        return jsonify({'warnings': [], 'count': 0, 'error': None})
    

@portfolio_bp.route('/api/analyze-thesis', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AI)
def analyze_investment_thesis():
    """
    API endpoint to analyze investment thesis quality.
    
    Request JSON:
        {
            "thesis": "My investment thesis text...",
            "company_id": 123,  // optional
            "expected_return": 25.0,  // optional
            "expected_timeframe": 12,  // optional (months)
            "confidence_score": 8  // optional (1-10)
        }
    
    Response JSON:
        {
            "success": true,
            "analysis": {
                "quality_score": 75,
                "quality_grade": "C",
                "summary": "...",
                "strengths": [...],
                "weaknesses": [...],
                "risk_flags": [...],
                "suggested_questions": [...],
                "missing_elements": [...],
                ...
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        thesis = data.get('thesis', '').strip()
        
        if not thesis:
            return jsonify({
                'success': False,
                'error': 'Thesis text is required'
            }), 400
        
        # Get company context if provided
        company_name = None
        ticker = None
        sector = None
        
        company_id = data.get('company_id')
        if company_id:
            company = Company.query.filter_by(
                id=company_id,
                user_id=current_user.id
            ).first()
            if company:
                company_name = company.name
                ticker = company.ticker_symbol
                sector = company.sector.display_name if company.sector else None
        
        # Analyze thesis
        result = analyze_thesis(
            thesis=thesis,
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            expected_return=data.get('expected_return'),
            expected_timeframe=data.get('expected_timeframe'),
            confidence_score=data.get('confidence_score')
        )
        
        return jsonify({
            'success': True,
            'analysis': result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error analyzing thesis: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze thesis'
        }), 500


@portfolio_bp.route('/api/thesis-quick-check', methods=['POST'])
@login_required
def quick_thesis_check():
    """
    Quick thesis assessment for real-time feedback.
    Lightweight check without full AI analysis.
    
    Request JSON:
        {"thesis": "My thesis text..."}
    
    Response JSON:
        {
            "word_count": 45,
            "has_minimum_length": true,
            "elements_detected": 2,
            "has_valuation": true,
            "has_risks": false,
            ...
        }
    """
    
    try:
        data = request.get_json()
        thesis = data.get('thesis', '') if data else ''
        
        result = get_quick_thesis_assessment(thesis)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in quick thesis check: {e}")
        return jsonify({
            'word_count': 0,
            'has_minimum_length': False,
            'elements_detected': 0,
            'quick_score': 0
        })


#TODO: Not intergrated to the system        
@portfolio_bp.route('/api/similar-decisions', methods=['POST'])
@login_required
def find_similar_decisions_api():
    """Find similar past decisions based on thesis text."""    
    try:
        data = request.get_json()
        thesis = data.get('thesis', '').strip()
        company_id = data.get('company_id')
        
        if not thesis or len(thesis) < 20:
            return jsonify({'similar_decisions': [], 'count': 0})
        
        similar = find_similar_past_decisions(
            user_id=current_user.id,
            thesis=thesis,
            company_id=company_id,
            max_results=5
        )
        
        return jsonify({
            'similar_decisions': [d.to_dict() for d in similar],
            'count': len(similar)
        })
    except Exception as e:
        logger.error(f"Error finding similar decisions: {e}")
        return jsonify({'similar_decisions': [], 'count': 0, 'error': str(e)})