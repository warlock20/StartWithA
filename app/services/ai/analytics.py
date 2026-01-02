"""
AI Prompt Analytics

Track prompt usage, costs, and performance for optimization.
"""

import logging
from typing import Optional, Dict, Any
from flask import has_request_context
from flask_login import current_user
from datetime import timedelta

from app import db
from app.models.prompt_management import PromptUsageLog
from app.utils.time_utils import now_utc
logger = logging.getLogger(__name__)


# Token pricing (as of 2025, in dollars per 1M tokens)
# Update these as providers change pricing
TOKEN_PRICING = {
    'claude-sonnet-4-20250514': {'input': 3.00, 'output': 15.00},
    'claude-opus-4-20241113': {'input': 15.00, 'output': 75.00},
    'claude-haiku-4-20250514': {'input': 0.25, 'output': 1.25},
    'gemini-2.0-flash-exp': {'input': 0.00, 'output': 0.00},  # Free tier
    'gemini-1.5-pro': {'input': 1.25, 'output': 5.00},
}


def log_prompt_usage(
    prompt_name: str,
    prompt_version: str,
    provider: str,
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    context_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> Optional[PromptUsageLog]:
    """
    Log prompt usage for analytics.

    Args:
        prompt_name: Name of the prompt (e.g., 'thesis_analysis_simple')
        prompt_version: Version of the prompt (e.g., '1.0')
        provider: AI provider (e.g., 'claude', 'gemini')
        model: Specific model used (e.g., 'claude-sonnet-4-20250514')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        latency_ms: Response time in milliseconds
        success: Whether the call succeeded
        error_message: Error message if failed
        context_data: Additional context (truncated if large)
        user_id: User ID (auto-detected from current_user if not provided)

    Returns:
        PromptUsageLog instance if logged successfully, None otherwise
    """
    try:
        # Auto-detect user_id from Flask context
        if user_id is None and has_request_context():
            if current_user.is_authenticated:
                user_id = current_user.id

        # Calculate total tokens
        total_tokens = 0
        if input_tokens:
            total_tokens += input_tokens
        if output_tokens:
            total_tokens += output_tokens

        # Estimate cost in cents
        estimated_cost_cents = _estimate_cost(model, input_tokens, output_tokens)

        # Truncate context_data if too large
        if context_data and len(str(context_data)) > 1000:
            context_data = {'_truncated': True, 'keys': list(context_data.keys())}

        # Create log entry
        log_entry = PromptUsageLog(
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            user_id=user_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_cents=estimated_cost_cents,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            context_data=context_data
        )

        db.session.add(log_entry)
        db.session.commit()

        logger.debug(
            f"Logged prompt usage: {prompt_name} v{prompt_version} "
            f"({total_tokens} tokens, ${estimated_cost_cents/100:.4f})"
        )

        return log_entry

    except Exception as e:
        logger.error(f"Failed to log prompt usage: {e}")
        # Don't let analytics failures break the main flow
        try:
            db.session.rollback()
        except:
            pass
        return None


def _estimate_cost(model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> int:
    """
    Estimate cost in cents based on model and token usage.

    Args:
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in cents (integer)
    """
    if not input_tokens and not output_tokens:
        return 0

    # Get pricing for this model
    pricing = TOKEN_PRICING.get(model)
    if not pricing:
        logger.warning(f"No pricing data for model {model}, using default")
        # Default to Sonnet pricing
        pricing = TOKEN_PRICING['claude-sonnet-4-20250514']

    # Calculate cost per million tokens, convert to cents
    input_cost = (input_tokens or 0) * pricing['input'] / 1_000_000
    output_cost = (output_tokens or 0) * pricing['output'] / 1_000_000

    total_cost_dollars = input_cost + output_cost
    total_cost_cents = int(total_cost_dollars * 100)

    return total_cost_cents


def get_prompt_analytics_summary(
    prompt_name: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get analytics summary for prompts.

    Args:
        prompt_name: Specific prompt to analyze (or None for all)
        days: Number of days to look back

    Returns:
        Dictionary with analytics data
    """

    cutoff_date = now_utc() - timedelta(days=days)

    query = PromptUsageLog.query.filter(
        PromptUsageLog.created_at >= cutoff_date
    )

    if prompt_name:
        query = query.filter(PromptUsageLog.prompt_name == prompt_name)

    logs = query.all()

    if not logs:
        return {
            'total_calls': 0,
            'total_tokens': 0,
            'total_cost_dollars': 0.0,
            'avg_latency_ms': 0,
            'success_rate': 0.0,
        }

    total_calls = len(logs)
    total_tokens = sum(log.total_tokens or 0 for log in logs)
    total_cost_cents = sum(log.estimated_cost_cents or 0 for log in logs)
    avg_latency = sum(log.latency_ms or 0 for log in logs if log.latency_ms) / total_calls
    success_count = sum(1 for log in logs if log.success)

    return {
        'total_calls': total_calls,
        'total_tokens': total_tokens,
        'total_cost_dollars': total_cost_cents / 100.0,
        'avg_latency_ms': int(avg_latency),
        'success_rate': (success_count / total_calls * 100) if total_calls > 0 else 0.0,
        'by_provider': _group_by(logs, 'provider'),
        'by_model': _group_by(logs, 'model'),
    }


def _group_by(logs, field):
    """Group logs by a field and count"""
    groups = {}
    for log in logs:
        key = getattr(log, field, 'unknown')
        if key not in groups:
            groups[key] = 0
        groups[key] += 1
    return groups
