"""
Comprehensive duplicate detection service for companies and ideas
"""

from flask import current_app
from app.models import Company, IdeaPipeline
from app import db
from difflib import SequenceMatcher
import re


class DuplicateDetectionService:
    """Service for detecting and preventing duplicate companies and ideas"""

    def __init__(self, user_id):
        self.user_id = user_id

    def normalize_name(self, name):
        """Normalize company name for comparison"""
        if not name:
            return ""

        # Convert to lowercase and remove common suffixes/prefixes
        normalized = name.lower().strip()

        # Remove common company suffixes
        suffixes = [
            'inc', 'inc.', 'incorporated', 'corp', 'corp.', 'corporation',
            'ltd', 'ltd.', 'limited', 'llc', 'l.l.c.', 'co', 'co.',
            'company', 'enterprises', 'holdings', 'group', 'plc', 'sa',
            'the', '&', 'and'
        ]

        for suffix in suffixes:
            # Remove suffix at the end
            if normalized.endswith(f' {suffix}'):
                normalized = normalized[:-len(f' {suffix}')]
            # Remove suffix at the beginning (like "The ")
            if normalized.startswith(f'{suffix} '):
                normalized = normalized[len(f'{suffix} '):]

        # Remove extra spaces and special characters
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def normalize_ticker(self, ticker):
        """Normalize ticker symbol for comparison"""
        if not ticker:
            return ""
        return ticker.upper().strip()

    def calculate_similarity(self, str1, str2):
        """Calculate similarity between two strings (0-1 scale)"""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def check_company_duplicates(self, name, ticker_symbol):
        """
        Check for company duplicates with comprehensive detection

        Returns:
        {
            'is_duplicate': bool,
            'exact_matches': [],
            'similar_matches': [],
            'suggestions': []
        }
        """
        result = {
            'is_duplicate': False,
            'exact_matches': [],
            'similar_matches': [],
            'suggestions': []
        }

        normalized_name = self.normalize_name(name)
        normalized_ticker = self.normalize_ticker(ticker_symbol)

        # Get all user's companies
        existing_companies = Company.query.filter_by(user_id=self.user_id).all()

        for company in existing_companies:
            existing_name = self.normalize_name(company.name)
            existing_ticker = self.normalize_ticker(company.ticker_symbol)

            # Exact ticker match
            if normalized_ticker and existing_ticker == normalized_ticker:
                if existing_name != normalized_name:
                    # Same ticker, different name - potential conflict
                    result['exact_matches'].append({
                        'type': 'ticker_conflict',
                        'company': company,
                        'message': f'Ticker {ticker_symbol} already exists for "{company.name}". Did you mean to update that company instead?'
                    })
                    result['is_duplicate'] = True
                else:
                    # Exact duplicate
                    result['exact_matches'].append({
                        'type': 'exact_duplicate',
                        'company': company,
                        'message': f'Company "{company.name}" ({company.ticker_symbol}) already exists.'
                    })
                    result['is_duplicate'] = True

            # Similar name detection
            elif normalized_name:
                name_similarity = self.calculate_similarity(normalized_name, existing_name)
                if name_similarity > 0.8:  # 80% similarity threshold
                    if normalized_ticker != existing_ticker:
                        # Similar name, different ticker - potential conflict
                        result['similar_matches'].append({
                            'type': 'name_similar_ticker_different',
                            'company': company,
                            'similarity': name_similarity,
                            'message': f'Similar company "{company.name}" exists with ticker {company.ticker_symbol}. Are these the same company?'
                        })
                        if name_similarity > 0.9:  # Very similar names should block
                            result['is_duplicate'] = True

        return result

    def check_idea_duplicates(self, name, ticker_symbol):
        """
        Check for idea duplicates including killed ideas

        Returns similar structure to check_company_duplicates
        """
        result = {
            'is_duplicate': False,
            'exact_matches': [],
            'similar_matches': [],
            'suggestions': []
        }

        normalized_name = self.normalize_name(name)
        normalized_ticker = self.normalize_ticker(ticker_symbol)

        # Check existing companies first
        company_check = self.check_company_duplicates(name, ticker_symbol)
        if company_check['exact_matches']:
            for match in company_check['exact_matches']:
                result['suggestions'].append({
                    'type': 'promote_existing_company',
                    'company': match['company'],
                    'message': f'Company "{match["company"].name}" already exists. Consider starting research instead of adding as idea.'
                })

        # Check existing ideas (including killed ones for warnings)
        existing_ideas = IdeaPipeline.query.filter_by(user_id=self.user_id).all()

        for idea in existing_ideas:
            existing_name = self.normalize_name(idea.name)
            existing_ticker = self.normalize_ticker(idea.ticker_symbol)

            # Exact ticker match
            if normalized_ticker and existing_ticker == normalized_ticker:
                if idea.status == 'killed':
                    # Allow re-adding killed ideas but warn user
                    result['suggestions'].append({
                        'type': 'killed_idea_exists',
                        'idea': idea,
                        'message': f'You previously killed idea "{idea.name}" ({idea.ticker_symbol}). Reason: {idea.kill_reason}. Continue anyway?'
                    })
                else:
                    # Active idea conflict
                    result['exact_matches'].append({
                        'type': 'active_idea_conflict',
                        'idea': idea,
                        'message': f'Active idea "{idea.name}" ({idea.ticker_symbol}) already exists with status: {idea.status}.'
                    })
                    result['is_duplicate'] = True

            # Similar name detection for active ideas
            elif normalized_name and idea.status != 'killed':
                name_similarity = self.calculate_similarity(normalized_name, existing_name)
                if name_similarity > 0.8:
                    result['similar_matches'].append({
                        'type': 'similar_active_idea',
                        'idea': idea,
                        'similarity': name_similarity,
                        'message': f'Similar idea "{idea.name}" exists with status: {idea.status}.'
                    })
                    if name_similarity > 0.9:
                        result['is_duplicate'] = True

        return result

    def get_resolution_suggestions(self, duplicate_check, entity_type='company'):
        """
        Generate user-friendly resolution suggestions

        Args:
            duplicate_check: Result from check_company_duplicates or check_idea_duplicates
            entity_type: 'company' or 'idea'

        Returns:
            List of suggested actions for the user
        """
        suggestions = []

        for match in duplicate_check['exact_matches']:
            if match['type'] == 'ticker_conflict':
                suggestions.append({
                    'action': 'update_existing',
                    'message': match['message'],
                    'button_text': 'Update Existing Company',
                    'url': f"/companies/{match['company'].id}/edit" if entity_type == 'company' else None
                })
            elif match['type'] == 'exact_duplicate':
                suggestions.append({
                    'action': 'view_existing',
                    'message': match['message'],
                    'button_text': 'View Existing Company',
                    'url': f"/companies/{match['company'].id}" if entity_type == 'company' else None
                })

        for match in duplicate_check['similar_matches']:
            suggestions.append({
                'action': 'compare',
                'message': match['message'],
                'button_text': 'Compare & Decide',
                'similarity': match.get('similarity', 0),
                'existing_entity': match.get('company') or match.get('idea')
            })

        for suggestion in duplicate_check['suggestions']:
            if suggestion['type'] == 'killed_idea_exists':
                suggestions.append({
                    'action': 'resurrect',
                    'message': suggestion['message'],
                    'button_text': 'Resurrect Previous Idea',
                    'existing_entity': suggestion['idea']
                })

        return suggestions