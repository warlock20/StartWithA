"""
Checkpoint Analysis Service

AI-powered analysis of DestinationCheckpoints. Evaluates whether investment
milestones are on track based on the user's research context.

Used by: Celery Beat task (daily), checkpoint_reminders view (display).
"""

import logging
from datetime import date, timedelta
from collections import defaultdict

from app import db
from app.models import DestinationCheckpoint, AIInsight
from app.services.ai import get_ai_service
from app.services.ai.config import AITaskType
from app.services.ai.prompt_service import prompt_service
from app.services.research_data_service import ResearchDataService
from app.constants import CHECKPOINT_ANALYSIS_WINDOW_DAYS, CHECKPOINT_ANALYSIS_DEDUP_HOURS
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

MAX_CONTEXT_LENGTH = 4000  # Truncate research context to control token usage


class CheckpointAnalysisService:

    @staticmethod
    def get_checkpoints_for_analysis(analysis_window_days=CHECKPOINT_ANALYSIS_WINDOW_DAYS):
        """
        Get active checkpoints grouped by user_id, within the analysis window.

        Returns checkpoints that are overdue (up to 30 days past) or upcoming
        within the window.

        Returns:
            dict[int, list[DestinationCheckpoint]]: Checkpoints grouped by user_id
        """
        today = date.today()
        earliest = today - timedelta(days=analysis_window_days)
        latest = today + timedelta(days=analysis_window_days)

        checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.status == 'Active',
            DestinationCheckpoint.target_date >= earliest,
            DestinationCheckpoint.target_date <= latest,
        ).order_by(DestinationCheckpoint.target_date.asc()).all()

        grouped = defaultdict(list)
        for cp in checkpoints:
            grouped[cp.user_id].append(cp)

        return dict(grouped)

    @staticmethod
    def has_recent_analysis(checkpoint_id, hours=CHECKPOINT_ANALYSIS_DEDUP_HOURS):
        """Check if a checkpoint was analyzed recently (dedup)."""
        cutoff = now_utc() - timedelta(hours=hours)
        return db.session.query(
            AIInsight.query.filter(
                AIInsight.context_type == 'checkpoint',
                AIInsight.context_id == checkpoint_id,
                AIInsight.is_active == True,
                AIInsight.created_at > cutoff,
            ).exists()
        ).scalar()

    @staticmethod
    def _build_prompt_variables(checkpoint, company, research_project):
        """
        Build template variables for the checkpoint_analysis prompt.

        Returns:
            dict: Variables for prompt_service.get_prompt()
        """
        today = date.today()
        days_until = (checkpoint.target_date - today).days

        # Build research context
        research_context = ""
        if research_project:
            research_context = ResearchDataService.get_all_text(
                research_project, include_metadata=True
            )
            if len(research_context) > MAX_CONTEXT_LENGTH:
                research_context = research_context[:MAX_CONTEXT_LENGTH] + "\n[... truncated]"

        if not research_context:
            research_context = "No research data available for this company."

        journey_notes = ""
        if company.journey_notes:
            journey_notes = f"\n\n## Company Journey Notes\n{company.journey_notes[:1000]}"

        return {
            'company_name': company.name,
            'ticker_symbol': company.ticker_symbol,
            'industry': company.industry or 'Unknown',
            'metric': checkpoint.metric,
            'expectation': checkpoint.expectation,
            'target_date': str(checkpoint.target_date),
            'days_until': days_until,
            'description': checkpoint.description or 'None provided',
            'research_context': research_context,
            'company_summary': company.summary or 'Not available',
            'journey_notes': journey_notes,
        }

    @staticmethod
    def analyze_checkpoint(checkpoint, company, research_project, user):
        """
        Run AI analysis on a single checkpoint and store as AIInsight.

        Args:
            checkpoint: DestinationCheckpoint instance
            company: Company instance
            research_project: ResearchProject instance (can be None)
            user: User instance (for token tracking)

        Returns:
            AIInsight or None if analysis fails
        """
        variables = CheckpointAnalysisService._build_prompt_variables(
            checkpoint, company, research_project
        )

        prompt_data = prompt_service.get_prompt_with_metadata(
            'checkpoint', 'checkpoint_analysis', **variables
        )
        prompt = prompt_data['prompt']
        system_context = prompt_data.get('system_context', '')

        ai_service = get_ai_service()

        result = ai_service.generate_json(
            prompt=prompt,
            max_tokens=prompt_data['metadata'].get('max_tokens', 1500),
            temperature=prompt_data['metadata'].get('temperature', 0.4),
            task=AITaskType.CHECKPOINT_ANALYSIS,
            system=system_context,
        )

        if not result:
            logger.warning(
                f"AI returned no result for checkpoint {checkpoint.id} "
                f"({company.ticker_symbol}: {checkpoint.metric})"
            )
            return None

        # Token tracking
        tokens_estimate = len(prompt) // 4 + len(str(result)) // 4
        user.increment_ai_tokens(tokens_estimate)

        # Expire old active insights for this checkpoint
        AIInsight.query.filter(
            AIInsight.context_type == 'checkpoint',
            AIInsight.context_id == checkpoint.id,
            AIInsight.is_active == True,
        ).update({'is_active': False}, synchronize_session=False)

        insight = AIInsight(
            user_id=checkpoint.user_id,
            insight_type='reminder',
            trigger_type='periodic',
            context_type='checkpoint',
            context_id=checkpoint.id,
            company_id=checkpoint.company_id,
            title=result.get('title', f'{checkpoint.metric} checkpoint analysis'),
            insight_text=result.get('analysis', ''),
            supporting_data={
                'status_assessment': result.get('status_assessment', 'insufficient_data'),
                'confidence': result.get('confidence', 0.0),
                'key_signals': result.get('key_signals', []),
                'checkpoint_metric': checkpoint.metric,
                'checkpoint_expectation': checkpoint.expectation,
            },
            confidence=result.get('confidence', 0.0),
            ai_provider='gemini',
            is_active=True,
            expires_at=now_utc() + timedelta(hours=25),
        )

        db.session.add(insight)
        db.session.flush()

        return insight

    @staticmethod
    def get_analysis_alerts(checkpoint_insights):
        """
        Build alert notifications from checkpoint insights for the dashboard header.

        Surfaces at_risk and likely_missed checkpoints as prominent alerts.

        Args:
            checkpoint_insights: dict from get_checkpoint_insights()

        Returns:
            list[dict]: Alert dicts with icon, message, status, company_id
        """
        alerts = []
        status_priority = {'likely_missed': 0, 'at_risk': 1}

        for checkpoint_id, insight in checkpoint_insights.items():
            if not insight.supporting_data:
                continue

            status = insight.supporting_data.get('status_assessment', '')
            if status not in status_priority:
                continue

            alerts.append({
                'icon': 'exclamation-triangle-fill' if status == 'likely_missed' else 'exclamation-circle',
                'status': status,
                'message': f"{insight.supporting_data.get('checkpoint_metric', 'Checkpoint')}: {insight.title}",
                'company_id': insight.company_id,
                'checkpoint_id': checkpoint_id,
                'confidence': insight.confidence,
            })

        # Sort: likely_missed first, then at_risk, then by confidence desc
        alerts.sort(key=lambda a: (status_priority.get(a['status'], 99), -(a['confidence'] or 0)))

        return alerts

    @staticmethod
    def get_checkpoint_insights(checkpoint_ids):
        """
        Get the latest active AI insights for a list of checkpoint IDs.

        Used by the checkpoint_reminders view to display analysis inline.

        Args:
            checkpoint_ids: list of DestinationCheckpoint IDs

        Returns:
            dict[int, AIInsight]: mapping checkpoint_id -> latest AIInsight
        """
        if not checkpoint_ids:
            return {}

        insights = AIInsight.query.filter(
            AIInsight.context_type == 'checkpoint',
            AIInsight.context_id.in_(checkpoint_ids),
            AIInsight.is_active == True,
        ).order_by(AIInsight.created_at.desc()).all()

        # Keep only the latest insight per checkpoint
        result = {}
        for insight in insights:
            if insight.context_id not in result:
                result[insight.context_id] = insight

        return result
