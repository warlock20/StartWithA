"""
Portfolio AI Analytics Celery Tasks

Background tasks for AI-powered portfolio analysis to avoid blocking the UI.
"""

import json
import logging
from app import db, create_app
from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def portfolio_ai_analysis_task(self, user_id, template_name='portfolio_raw_trade_analysis'):
    """
    Celery task for AI-powered portfolio analysis.
    Runs in background to avoid blocking the UI during long AI calls.

    Args:
        user_id: User ID whose portfolio to analyze
        template_name: Which analysis template to use
            - 'portfolio_raw_trade_analysis': Deep behavioral analysis (default)
            - 'portfolio_complete_analysis': Quick overview

    Returns:
        JSON string with status and insights
    """
    app = create_app()
    with app.app_context():
        try:
            logger.info(f"TASK {self.request.id}: Starting portfolio AI analysis for user {user_id}")

            # Import here to avoid circular dependencies
            from app.services.portfolio_ai_analytics import PortfolioAIAnalytics

            # Create analytics service
            analytics = PortfolioAIAnalytics(user_id=user_id)

            # Run the analysis (force_refresh=True to actually generate)
            logger.info(f"TASK {self.request.id}: Calling AI service with template '{template_name}'...")

            if template_name == 'portfolio_raw_trade_analysis':
                result = analytics.get_deep_behavioral_insights(force_refresh=True)
            else:
                result = analytics.get_quick_insights(force_refresh=True)

            # Task completed successfully
            logger.info(f"TASK {self.request.id}: Completed successfully")

            # Return result as JSON string
            return json.dumps({
                "status": "success",
                "message": f"Portfolio AI analysis completed for user {user_id}",
                "insights": result
            })

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Failed - {e}", exc_info=True)
            db.session.rollback()

            # Return error as JSON string
            return json.dumps({
                "status": "failed",
                "message": str(e),
                "insights": None
            })
