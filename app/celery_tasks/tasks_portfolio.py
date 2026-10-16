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

"""
Portfolio AI Analytics Celery Tasks

Background tasks for AI-powered portfolio analysis to avoid blocking the UI.
"""

import logging

from app.celery_tasks.base import background_task
from app.models import PortfolioUIInsight, PortfolioPosition, User
from app.utils.time_utils import parse_date_to_date_object
from app.services.portfolio_ai_analytics import PortfolioAIAnalytics

logger = logging.getLogger(__name__)


@background_task()
def portfolio_ai_analysis_task(self, task, user_id, template_name='portfolio_raw_trade_analysis'):
    """
    Celery task for AI-powered portfolio analysis.
    Runs in background to avoid blocking the UI during long AI calls.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID whose portfolio to analyze
        template_name: Which analysis template to use
            - 'portfolio_raw_trade_analysis': Deep behavioral analysis (default)
            - 'portfolio_complete_analysis': Quick overview
    """
    logger.info(f"TASK {self.request.id}: Starting portfolio AI analysis for user {user_id}")

    analytics = PortfolioAIAnalytics(user_id=user_id)

    # Run the analysis (force_refresh=True to actually generate)
    logger.info(f"TASK {self.request.id}: Calling AI service with template '{template_name}'...")

    if template_name == 'portfolio_raw_trade_analysis':
        result, tokens_used = analytics.get_deep_behavioral_insights(force_refresh=True)
    elif template_name == 'sector_momentum_analysis':
        result, tokens_used = analytics.get_sector_momentum_analysis(force_refresh=True)
    elif template_name == 'tax_optimization_analysis':
        result, tokens_used = analytics.get_tax_optimization_analysis(force_refresh=True)
    else:
        result, tokens_used = analytics.get_quick_insights(force_refresh=True)

    # Track token usage
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

    return {
        "analysis": result,
        "tokens_used": tokens_used,
        "message": "Portfolio AI analysis completed successfully!"
    }
