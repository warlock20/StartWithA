"""
Portfolio AI Analytics Celery Tasks

Background tasks for AI-powered portfolio analysis to avoid blocking the UI.
"""

import json
import logging
from app import db, create_app
from celery_app import celery
from app.models import BackgroundTask, PortfolioUIInsight, PortfolioPosition
from app.utils.time_utils import now_utc, parse_date_to_date_object
from app.services.portfolio_ai_analytics import PortfolioAIAnalytics

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def portfolio_ai_analysis_task(self, task_id, user_id, template_name='portfolio_raw_trade_analysis'):
    """
    Celery task for AI-powered portfolio analysis.
    Runs in background to avoid blocking the UI during long AI calls.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID whose portfolio to analyze
        template_name: Which analysis template to use
            - 'portfolio_raw_trade_analysis': Deep behavioral analysis (default)
            - 'portfolio_complete_analysis': Quick overview

    Returns:
        JSON string with status and insights
    """
    app = create_app()
    with app.app_context():
        
        # Get task record
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: BackgroundTask {task_id} not found")
            return json.dumps({"status": "failed", "message": "Task record not found"})

        try:
            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Starting portfolio AI analysis for user {user_id}")

            # Create analytics service
            analytics = PortfolioAIAnalytics(user_id=user_id)

            # Run the analysis (force_refresh=True to actually generate)
            logger.info(f"TASK {self.request.id}: Calling AI service with template '{template_name}'...")

            if template_name == 'portfolio_raw_trade_analysis':
                result, tokens_used = analytics.get_deep_behavioral_insights(force_refresh=True)
            else:
                result, tokens_used = analytics.get_quick_insights(force_refresh=True)

            # Track token usage
            from app.models.user import User
            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(tokens_used)
                logger.info(f"TASK {self.request.id}: Incremented {tokens_used} tokens for user {user_id}")
            else:
                logger.warning(f"TASK {self.request.id}: User {user_id} not found for token tracking")

            # Save to historical insights table for trend tracking
            try:
                # Get portfolio context at time of analysis
                positions = PortfolioPosition.query.filter_by(
                    user_id=user_id,
                    is_active=True
                ).all()
                portfolio_value = sum(p.current_value or 0 for p in positions)
                position_count = len(positions)

                # Get last transaction date from result metadata if available
                last_txn_date = None
                if result and isinstance(result, dict):
                    metadata = result.get('metadata', {})
                    last_txn_str = metadata.get('last_transaction_date')
                    if last_txn_str:
                        last_txn_date = parse_date_to_date_object(last_txn_str)

                PortfolioUIInsight.save_analysis(
                    user_id=user_id,
                    template_name=template_name,
                    insights=result,
                    tokens_used=tokens_used,
                    portfolio_value=portfolio_value,
                    position_count=position_count,
                    last_transaction_date=last_txn_date
                )
                logger.info(f"TASK {self.request.id}: Saved insights to history table")
            except Exception as save_error:
                logger.warning(f"TASK {self.request.id}: Failed to save to history: {save_error}")
                # Don't fail the task if history save fails

            # Task completed successfully
            logger.info(f"TASK {self.request.id}: Completed successfully")

            # Update task status to completed
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                "analysis": result,
                "tokens_used": tokens_used,
                "message": "Portfolio AI analysis completed successfully!"
            })
            db.session.commit()

            # Return result as JSON string
            return json.dumps({
                "status": "success",
                "message": f"Portfolio AI analysis completed for user {user_id}",
                "insights": result,
                "tokens_used": tokens_used
            })

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Failed - {e}", exc_info=True)

            # Update task status to failed
            task.status = 'failed'
            task.completed_at = now_utc()
            task.error_message = str(e)
            db.session.commit()

            # Return error as JSON string
            return json.dumps({
                "status": "failed",
                "message": str(e),
                "insights": None
            })
