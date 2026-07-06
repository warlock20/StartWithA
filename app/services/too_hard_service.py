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

# app/services/too_hard_service.py

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from app import cache
from app.models.idea_pipeline import IdeaPipeline
from app.models.research import ResearchProject
from app.models.company import Company


@dataclass
class TooHardItem:
    """Unified representation of rejected companies from multiple sources"""
    company_name: str
    ticker: Optional[str]
    sector: Optional[str]
    rejection_stage: str  # 'kill_checklist', 'mid_research', 'full_analysis'
    rejection_date: Optional[datetime]
    time_invested_hours: float
    reason: Optional[str]
    within_coc: Optional[str]  # 'yes', 'no', 'unsure'
    confidence: Optional[int] = None  # For full analysis only
    notes: Optional[str] = None
    source_type: str = None  # 'IdeaPipeline' or 'ResearchProject'
    source_id: int = None
    company_id: Optional[int] = None


class TooHardBasketService:
    """Service to fetch and analyze all rejected companies"""

    @staticmethod
    def get_all_too_hard_companies(user_id: int, filters: Optional[Dict[str, Any]] = None) -> List[TooHardItem]:
        """
        Returns unified list of all rejected companies from:
        1. IdeaPipeline (status='killed')
        2. ResearchProject (decision='pass')

        Args:
            user_id: User ID to fetch data for
            filters: Optional dictionary with keys:
                - rejection_stage: Filter by stage ('kill_checklist', 'mid_research', 'full_analysis')
                - sector: Filter by sector name
                - within_coc: Filter by circle of competence ('yes', 'no', 'unsure')
                - search: Search in company name or ticker

        Returns:
            List of TooHardItem objects
        """
        items = []

        # 1. Get killed ideas from Kill Checklist
        killed_ideas = IdeaPipeline.query.filter_by(
            user_id=user_id,
            status='killed'
        ).all()

        for idea in killed_ideas:
            # Get sector info
            sector = None
            if idea.sector_id:
                sector = idea.sector.display_name if idea.sector else None

            items.append(TooHardItem(
                company_name=idea.name,
                ticker=idea.ticker_symbol,
                sector=sector,
                rejection_stage='kill_checklist',
                rejection_date=idea.killed_at,
                time_invested_hours=0.5,  # Avg kill checklist time
                reason=idea.kill_reason,
                within_coc=idea.within_circle_of_competence,
                notes=idea.initial_notes,
                source_type='IdeaPipeline',
                source_id=idea.id,
                company_id=idea.company_id
            ))

        # 2. Get all passed research projects (decision='pass')
        # This includes both mid-research passes (too hard) and full analysis passes
        passed_projects = ResearchProject.query.filter_by(
            user_id=user_id,
            decision='pass'
        ).all()

        for project in passed_projects:
            # Get sector info
            sector = None
            if project.sector_id:
                sector = project.sector.display_name if project.sector else None
            elif project.company and project.company.sector_id:
                sector = project.company.sector.display_name if project.company.sector else None

            # Determine if this was a mid-research pass (too hard) or full analysis pass
            is_mid_research = bool(project.too_hard_reason)

            if is_mid_research:
                items.append(TooHardItem(
                    company_name=project.company.name if project.company else 'Unknown',
                    ticker=project.company.ticker_symbol if project.company else None,
                    sector=sector,
                    rejection_stage='mid_research',
                    rejection_date=project.abandoned_at or project.decision_date,
                    time_invested_hours=project.total_hours_spent or 0,
                    reason=project.too_hard_reason,
                    within_coc=project.within_circle_of_competence,
                    notes=project.too_hard_notes,
                    source_type='ResearchProject',
                    source_id=project.id,
                    company_id=project.company_id
                ))
            else:
                items.append(TooHardItem(
                    company_name=project.company.name if project.company else 'Unknown',
                    ticker=project.company.ticker_symbol if project.company else None,
                    sector=sector,
                    rejection_stage='full_analysis',
                    rejection_date=project.decision_date,
                    time_invested_hours=project.total_hours_spent or 0,
                    reason='Completed full analysis',
                    within_coc=project.within_circle_of_competence,
                    confidence=project.decision_confidence,
                    notes=project.decision_notes,
                    source_type='ResearchProject',
                    source_id=project.id,
                    company_id=project.company_id
                ))

        # Apply filters if provided
        if filters:
            items = TooHardBasketService._apply_filters(items, filters)

        # Sort by rejection date (most recent first)
        items.sort(key=lambda x: x.rejection_date or datetime.min, reverse=True)

        return items

    @staticmethod
    @cache.memoize(timeout=300)
    def get_analytics(user_id: int) -> Dict[str, Any]:
        """
        Generate Circle of Competence and sector analytics

        Args:
            user_id: User ID to generate analytics for

        Returns:
            Dictionary with:
                - sector_stats: Analytics by sector
                - coc_stats: Overall Circle of Competence statistics
                - recommendations: AI-generated recommendations
        """
        items = TooHardBasketService.get_all_too_hard_companies(user_id)

        # Group by sector
        sector_stats = {}
        coc_stats = {'yes': 0, 'no': 0, 'unsure': 0}

        for item in items:
            # Sector analysis
            sector = item.sector or 'Uncategorized'
            if sector not in sector_stats:
                sector_stats[sector] = {
                    'total_analyzed': 0,
                    'killed': 0,
                    'mid_research_pass': 0,
                    'passed_full': 0,
                    'total_time': 0,
                    'within_coc_yes': 0,
                    'within_coc_no': 0
                }

            sector_stats[sector]['total_analyzed'] += 1
            sector_stats[sector]['total_time'] += item.time_invested_hours or 0

            if item.rejection_stage == 'kill_checklist':
                sector_stats[sector]['killed'] += 1
            elif item.rejection_stage == 'mid_research':
                sector_stats[sector]['mid_research_pass'] += 1
            else:
                sector_stats[sector]['passed_full'] += 1

            if item.within_coc == 'yes':
                sector_stats[sector]['within_coc_yes'] += 1
                coc_stats['yes'] += 1
            elif item.within_coc == 'no':
                sector_stats[sector]['within_coc_no'] += 1
                coc_stats['no'] += 1
            else:
                coc_stats['unsure'] += 1

        # Also get invested companies by sector for comparison
        invested_projects = ResearchProject.query.filter_by(
            user_id=user_id,
            status='completed',
            decision='invest'
        ).all()

        for project in invested_projects:
            # Get sector info
            sector = None
            if project.sector_id:
                sector = project.sector.display_name if project.sector else None
            elif project.company and project.company.sector_id:
                sector = project.company.sector.display_name if project.company.sector else None

            sector = sector or 'Uncategorized'

            if sector not in sector_stats:
                sector_stats[sector] = {
                    'total_analyzed': 0,
                    'killed': 0,
                    'mid_research_pass': 0,
                    'passed_full': 0,
                    'invested': 0,
                    'total_time': 0
                }
            sector_stats[sector]['invested'] = sector_stats[sector].get('invested', 0) + 1

        # Calculate sector scores
        for sector, stats in sector_stats.items():
            total = stats['total_analyzed']
            invested = stats.get('invested', 0)

            # Success rate = invested / (total analyzed + invested)
            stats['success_rate'] = (invested / (total + invested) * 100) if (total + invested) > 0 else 0

            # Circle of Competence score
            stats['coc_confidence'] = (stats['within_coc_yes'] / total * 100) if total > 0 else 0

        return {
            'sector_stats': sector_stats,
            'coc_stats': coc_stats,
            'recommendations': TooHardBasketService._generate_recommendations(sector_stats)
        }

    @staticmethod
    def _apply_filters(items: List[TooHardItem], filters: Dict[str, Any]) -> List[TooHardItem]:
        """Apply filters to list of TooHardItem objects"""
        filtered = items

        if 'rejection_stage' in filters and filters['rejection_stage']:
            filtered = [item for item in filtered if item.rejection_stage == filters['rejection_stage']]

        if 'sector' in filters and filters['sector']:
            filtered = [item for item in filtered if item.sector == filters['sector']]

        if 'within_coc' in filters and filters['within_coc']:
            filtered = [item for item in filtered if item.within_coc == filters['within_coc']]

        if 'search' in filters and filters['search']:
            search_term = filters['search'].lower()
            filtered = [
                item for item in filtered
                if (search_term in (item.company_name or '').lower()) or
                   (item.ticker and search_term in item.ticker.lower())
            ]

        return filtered

    @staticmethod
    def _generate_recommendations(sector_stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
        """Generate AI-like recommendations based on patterns"""
        recs = []

        # Exclude non-sectors from recommendations
        excluded_sectors = {'Uncategorized', 'Unknown', 'None', ''}

        for sector, stats in sector_stats.items():
            # Skip non-sectors
            if sector in excluded_sectors:
                continue

            # Pattern 1: High rejection rate + low CoC
            if stats['total_analyzed'] >= 3 and stats['coc_confidence'] < 30:
                recs.append({
                    'type': 'avoid',
                    'sector': sector,
                    'message': f"You're struggling with {sector} (analyzed {stats['total_analyzed']}, low confidence). Consider avoiding this sector.",
                    'severity': 'high'
                })

            # Pattern 2: High success rate + high CoC
            if stats.get('success_rate', 0) > 30 and stats['coc_confidence'] > 70:
                recs.append({
                    'type': 'strength',
                    'sector': sector,
                    'message': f"{sector} is your strength! {stats.get('invested', 0)} investments from {stats['total_analyzed'] + stats.get('invested', 0)} analyzed.",
                    'severity': 'positive'
                })

            # Pattern 3: Many killed early - good filtering
            if stats['killed'] >= 5 and stats['total_analyzed'] >= 5:
                kill_rate = stats['killed'] / stats['total_analyzed'] * 100
                if kill_rate > 70:
                    recs.append({
                        'type': 'efficiency',
                        'sector': sector,
                        'message': f"Great filtering in {sector}! {kill_rate:.0f}% caught early, saving research time.",
                        'severity': 'positive'
                    })

        return recs

    @staticmethod
    def get_sector_summary(user_id: int, sector_name: str) -> Dict[str, Any]:
        """
        Get summary statistics for a specific sector

        Args:
            user_id: User ID
            sector_name: Name of the sector to analyze

        Returns:
            Dictionary with sector-specific statistics
        """
        items = TooHardBasketService.get_all_too_hard_companies(
            user_id,
            filters={'sector': sector_name}
        )

        if not items:
            return {
                'sector': sector_name,
                'total_rejected': 0,
                'breakdown': {},
                'avg_time_invested': 0,
                'coc_breakdown': {}
            }

        # Calculate breakdown
        breakdown = {
            'kill_checklist': 0,
            'mid_research': 0,
            'full_analysis': 0
        }

        coc_breakdown = {
            'yes': 0,
            'no': 0,
            'unsure': 0
        }

        total_time = 0

        for item in items:
            breakdown[item.rejection_stage] += 1
            total_time += item.time_invested_hours or 0

            if item.within_coc:
                coc_breakdown[item.within_coc] += 1

        return {
            'sector': sector_name,
            'total_rejected': len(items),
            'breakdown': breakdown,
            'avg_time_invested': total_time / len(items) if items else 0,
            'coc_breakdown': coc_breakdown
        }
