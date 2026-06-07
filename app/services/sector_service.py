# app/services/sector_service.py

from collections import defaultdict
from app import db
from app.models import Sector, Company, ResearchProject, IdeaPipeline
from sqlalchemy import func


class SectorService:
    """
    Service layer for Sector operations.
    Handles business logic for sector management, search, and analytics.
    """

    @staticmethod
    def find_or_create_sector(user_id, sector_name, auto_create=True):
        """
        Find existing sector by name or create new one.

        Args:
            user_id: User ID
            sector_name: Sector name to search for
            auto_create: If True, create sector if not found

        Returns:
            Sector object or None
        """
        if not sector_name or not sector_name.strip():
            return None

        sector_name = sector_name.strip()

        # Try exact slug match first
        slug = Sector.make_slug(sector_name)
        sector = Sector.query.filter_by(
            user_id=user_id,
            slug=slug
        ).first()

        if sector:
            return sector

        # Try alias/fuzzy match
        all_sectors = Sector.query.filter_by(user_id=user_id, status='active').all()
        for s in all_sectors:
            if s.matches_name(sector_name):
                return s

        # Create new sector if auto_create is enabled
        if auto_create:
            sector = Sector(
                user_id=user_id,
                name=sector_name,
                display_name=sector_name.title(),
                slug=slug,
                is_default=False
            )
            db.session.add(sector)
            db.session.flush()  # Get ID without committing
            return sector

        return None

    @staticmethod
    def get_sector_autocomplete(user_id, query, limit=10):
        """
        Get sector suggestions for autocomplete.

        Args:
            user_id: User ID
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of Sector objects sorted by match quality
        """
        if not query or len(query) < 1:
            # Return recently used sectors
            return Sector.query.filter_by(
                user_id=user_id,
                status='active'
            ).order_by(Sector.last_researched.desc().nullslast()).limit(limit).all()

        sectors = Sector.query.filter_by(
            user_id=user_id,
            status='active'
        ).all()

        # Score sectors by match quality
        matches = []
        for sector in sectors:
            score = SectorService._match_score(sector, query)
            if score > 0:
                matches.append({
                    'sector': sector,
                    'score': score
                })

        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)

        return [m['sector'] for m in matches[:limit]]

    @staticmethod
    def _match_score(sector, query):
        """
        Calculate match score for autocomplete ranking.
        Higher score = better match.

        Args:
            sector: Sector object
            query: Search query string

        Returns:
            Integer score (0-100)
        """
        query_lower = query.lower().strip()

        # Exact slug match (highest priority)
        if sector.slug == query_lower:
            return 100

        # Display name starts with query (very high)
        if sector.display_name.lower().startswith(query_lower):
            return 90

        # Display name contains query (high)
        if query_lower in sector.display_name.lower():
            return 70

        # Name contains query (medium)
        if query_lower in sector.name.lower():
            return 60

        # Alias match (medium-low)
        if sector.aliases:
            for alias in sector.aliases:
                if query_lower in alias.lower():
                    return 50

        # No match
        return 0

    @staticmethod
    def merge_sectors(user_id, source_sector_id, target_sector_id):
        """
        Merge one sector into another.
        All references to source sector will point to target sector.

        Args:
            user_id: User ID (for security check)
            source_sector_id: ID of sector to merge from
            target_sector_id: ID of sector to merge into

        Returns:
            True if successful, False otherwise
        """
        source = Sector.query.get(source_sector_id)
        target = Sector.query.get(target_sector_id)

        # Validation
        if not source or not target:
            return False

        if source.user_id != user_id or target.user_id != user_id:
            return False

        if source.id == target.id:
            return False

        # Update all references
        Company.query.filter_by(sector_id=source_sector_id).update({'sector_id': target_sector_id})

        # Note: SectorAnalysis has unique constraint on (user_id, sector_id)
        # So we need to handle potential conflicts
        existing_target_analysis = db.session.query(func.count()).filter_by(
            user_id=user_id,
            sector_id=target_sector_id
        ).scalar()

        if existing_target_analysis > 0:
            # Target already has analysis, delete source analyses
            from app.models import SectorAnalysis
            SectorAnalysis.query.filter_by(sector_id=source_sector_id).delete()
        else:
            # Safe to migrate
            from app.models import SectorAnalysis
            SectorAnalysis.query.filter_by(sector_id=source_sector_id).update({'sector_id': target_sector_id})

        ResearchProject.query.filter_by(sector_id=source_sector_id).update({'sector_id': target_sector_id})
        IdeaPipeline.query.filter_by(sector_id=source_sector_id).update({'sector_id': target_sector_id})

        # Mark source as merged
        source.status = 'merged'
        source.merged_into_id = target_sector_id

        # Update target analytics
        target.update_analytics()

        db.session.commit()
        return True

    @staticmethod
    def get_sector_analytics(user_id, sector_id=None):
        """
        Get comprehensive sector analytics.

        Args:
            user_id: User ID
            sector_id: Optional specific sector ID, if None returns all sectors

        Returns:
            Sector object or dict with categorized sectors
        """
        if sector_id:
            sector = Sector.query.get(sector_id)
            if sector and sector.user_id == user_id:
                sector.update_analytics()
                return sector
            return None

        # Get all active sectors for user
        sectors = Sector.query.filter_by(user_id=user_id, status='active').all()

        if not sectors:
            return {
                'all': [], 'by_competence': [], 'by_success': [],
                'by_activity': [], 'by_time': [],
                'total_sectors': 0, 'active_research': 0
            }

        sector_ids = [s.id for s in sectors]

        # Batch: company counts per sector (1 query instead of N)
        company_counts = dict(
            db.session.query(Company.sector_id, func.count(Company.id))
            .filter(Company.user_id == user_id, Company.sector_id.in_(sector_ids))
            .group_by(Company.sector_id).all()
        )

        # Batch: all research projects for user's sectors (1 query instead of N)
        all_projects = ResearchProject.query.filter(
            ResearchProject.user_id == user_id,
            ResearchProject.sector_id.in_(sector_ids)
        ).all()

        # Group projects by sector in Python
        projects_by_sector = defaultdict(list)
        for p in all_projects:
            projects_by_sector[p.sector_id].append(p)

        # Apply analytics to each sector from batch data (no per-sector queries)
        for sector in sectors:
            sid = sector.id
            sector.total_companies = company_counts.get(sid, 0)
            sector_projects = projects_by_sector.get(sid, [])
            sector.companies_analyzed = len([p for p in sector_projects if p.status == 'completed'])
            sector.companies_invested = len([p for p in sector_projects if p.decision == 'invest'])
            sector.total_research_hours = sum(p.total_hours_spent or 0 for p in sector_projects)
            sector.coc_yes_count = len([p for p in sector_projects if p.within_circle_of_competence == 'yes'])
            sector.coc_no_count = len([p for p in sector_projects if p.within_circle_of_competence == 'no'])
            sector.coc_unsure_count = len([p for p in sector_projects if p.within_circle_of_competence == 'unsure'])
            if sector_projects:
                latest = max(sector_projects, key=lambda p: p.last_worked_at or p.created_at)
                sector.last_researched = latest.last_worked_at or latest.created_at

        # Return categorized results
        return {
            'all': sectors,
            'by_competence': sorted(sectors, key=lambda s: s.coc_confidence, reverse=True),
            'by_success': sorted(sectors, key=lambda s: s.success_rate, reverse=True),
            'by_activity': sorted(sectors, key=lambda s: s.companies_analyzed, reverse=True),
            'by_time': sorted(sectors, key=lambda s: s.total_research_hours, reverse=True),
            'total_sectors': len(sectors),
            'active_research': sum(1 for s in sectors if s.companies_analyzed > 0)
        }

    @staticmethod
    def get_user_sectors_list(user_id, include_inactive=False):
        """
        Get simple list of user's sectors for dropdowns.

        Args:
            user_id: User ID
            include_inactive: Include archived/merged sectors

        Returns:
            List of Sector objects ordered by display name
        """
        query = Sector.query.filter_by(user_id=user_id)

        if not include_inactive:
            query = query.filter_by(status='active')

        return query.order_by(Sector.display_name).all()

    @staticmethod
    def archive_sector(user_id, sector_id):
        """
        Archive a sector (soft delete).

        Args:
            user_id: User ID
            sector_id: Sector ID to archive

        Returns:
            True if successful, False otherwise
        """
        sector = Sector.query.get(sector_id)

        if not sector or sector.user_id != user_id:
            return False

        sector.status = 'archived'
        db.session.commit()
        return True

    @staticmethod
    def restore_sector(user_id, sector_id):
        """
        Restore an archived sector.

        Args:
            user_id: User ID
            sector_id: Sector ID to restore

        Returns:
            True if successful, False otherwise
        """
        sector = Sector.query.get(sector_id)

        if not sector or sector.user_id != user_id:
            return False

        sector.status = 'active'
        db.session.commit()
        return True

    @staticmethod
    def update_sector_metadata(user_id, sector_id, **kwargs):
        """
        Update sector metadata (description, characteristics, metrics, etc.).

        Args:
            user_id: User ID
            sector_id: Sector ID
            **kwargs: Fields to update (description, key_characteristics, typical_metrics, etc.)

        Returns:
            Updated Sector object or None
        """
        sector = Sector.query.get(sector_id)

        if not sector or sector.user_id != user_id:
            return None

        # Allowed fields
        allowed_fields = [
            'description', 'key_characteristics', 'typical_metrics',
            'aliases', 'icon', 'color', 'category', 'display_name'
        ]

        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(sector, field, value)

        db.session.commit()
        return sector

    @staticmethod
    def get_sector_companies(sector_id, user_id):
        """
        Get all companies in a sector.

        Args:
            sector_id: Sector ID
            user_id: User ID

        Returns:
            List of Company objects
        """
        return Company.query.filter_by(
            user_id=user_id,
            sector_id=sector_id
        ).order_by(Company.name).all()

    @staticmethod
    def get_sector_stats(sector_id, user_id):
        """
        Get detailed statistics for a sector.

        Args:
            sector_id: Sector ID
            user_id: User ID

        Returns:
            Dict with sector statistics
        """
        sector = Sector.query.get(sector_id)

        if not sector or sector.user_id != user_id:
            return None

        # Get research projects
        projects = ResearchProject.query.filter_by(
            user_id=user_id,
            sector_id=sector_id
        ).all()

        # Get ideas
        ideas = IdeaPipeline.query.filter_by(
            user_id=user_id,
            sector_id=sector_id
        ).all()

        # Calculate stats
        total_projects = len(projects)
        completed_projects = len([p for p in projects if p.status == 'completed'])
        invested_projects = len([p for p in projects if p.decision == 'invest'])
        passed_projects = len([p for p in projects if p.decision == 'pass'])

        total_ideas = len(ideas)
        killed_ideas = len([i for i in ideas if i.status == 'killed'])
        survived_ideas = len([i for i in ideas if i.status == 'survived'])

        return {
            'sector': sector,
            'companies_count': sector.total_companies,
            'research_projects': {
                'total': total_projects,
                'completed': completed_projects,
                'invested': invested_projects,
                'passed': passed_projects,
                'success_rate': (invested_projects / completed_projects * 100) if completed_projects > 0 else 0
            },
            'ideas': {
                'total': total_ideas,
                'killed': killed_ideas,
                'survived': survived_ideas,
                'survival_rate': (survived_ideas / total_ideas * 100) if total_ideas > 0 else 0
            },
            'time_invested': sector.total_research_hours,
            'circle_of_competence': {
                'yes': sector.coc_yes_count,
                'no': sector.coc_no_count,
                'unsure': sector.coc_unsure_count,
                'confidence': sector.coc_confidence
            }
        }
