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

# app/utils/company_detection.py
"""
Utility functions for detecting and matching company mentions in text.
"""

import re
from typing import List, Dict
from app.models import Company


def detect_company_mentions(text: str, user_id: int) -> List[Dict]:
    """
    Detect company mentions in text and return matching companies from the database.

    Args:
        text: The text content to analyze
        user_id: The user ID to filter tracked companies

    Returns:
        List of dictionaries containing matched companies with confidence scores:
        [
            {
                'company': Company object,
                'confidence': 'high' | 'medium' | 'low',
                'matched_text': 'The text that matched',
                'match_type': 'ticker' | 'exact_name' | 'partial_name'
            },
            ...
        ]
    """
    if not text or not text.strip():
        return []

    # Get all tracked companies for the user
    tracked_companies = Company.query.filter_by(user_id=user_id).all()

    if not tracked_companies:
        return []

    matches = []
    seen_company_ids = set()

    # Clean text for better matching
    text_upper = text.upper()

    for company in tracked_companies:
        # Skip if already matched this company
        if company.id in seen_company_ids:
            continue

        # Priority 1: Exact ticker match (highest confidence)
        ticker = company.ticker_symbol.upper()
        # Match ticker as standalone word (not part of another word)
        ticker_pattern = r'\b' + re.escape(ticker) + r'\b'
        if re.search(ticker_pattern, text_upper):
            matches.append({
                'company': company,
                'confidence': 'high',
                'matched_text': company.ticker_symbol,
                'match_type': 'ticker'
            })
            seen_company_ids.add(company.id)
            continue

        # Priority 2: Exact company name match (high confidence)
        company_name = company.name
        if company_name:
            # Case-insensitive search for exact name
            name_pattern = r'\b' + re.escape(company_name) + r'\b'
            if re.search(name_pattern, text, re.IGNORECASE):
                matches.append({
                    'company': company,
                    'confidence': 'high',
                    'matched_text': company_name,
                    'match_type': 'exact_name'
                })
                seen_company_ids.add(company.id)
                continue

            # Priority 3: Partial name match without common suffixes (medium confidence)
            # Remove common suffixes like Inc., Corp., Ltd., etc.
            clean_name = re.sub(r'\s+(Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|Co\.?|Company)$',
                               '', company_name, flags=re.IGNORECASE).strip()

            if clean_name and clean_name != company_name:
                clean_pattern = r'\b' + re.escape(clean_name) + r'\b'
                if re.search(clean_pattern, text, re.IGNORECASE):
                    matches.append({
                        'company': company,
                        'confidence': 'medium',
                        'matched_text': clean_name,
                        'match_type': 'partial_name'
                    })
                    seen_company_ids.add(company.id)
                    continue

    # Sort matches by confidence (high first, then medium, then low)
    confidence_order = {'high': 0, 'medium': 1, 'low': 2}
    matches.sort(key=lambda x: (confidence_order[x['confidence']], x['company'].name))

    return matches


def get_company_suggestions_for_text(text: str, user_id: int) -> Dict:
    """
    Get company suggestions for text with categorization by confidence.

    Args:
        text: The text content to analyze
        user_id: The user ID to filter tracked companies

    Returns:
        Dictionary with categorized suggestions:
        {
            'high_confidence': [list of company dicts],
            'medium_confidence': [list of company dicts],
            'total_matches': int
        }
    """
    matches = detect_company_mentions(text, user_id)

    result = {
        'high_confidence': [],
        'medium_confidence': [],
        'total_matches': len(matches)
    }

    for match in matches:
        company_dict = {
            'id': match['company'].id,
            'name': match['company'].name,
            'ticker': match['company'].ticker_symbol,
            'sector': match['company'].sector,
            'matched_text': match['matched_text'],
            'match_type': match['match_type']
        }

        if match['confidence'] == 'high':
            result['high_confidence'].append(company_dict)
        else:
            result['medium_confidence'].append(company_dict)

    return result
