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
AI Prompt Analytics

Track prompt usage, costs, and performance for optimization.
"""

import logging
from typing import Optional, Dict, Any
from flask import has_request_context
from flask_login import current_user

from app import db
from app.models.prompt_management import PromptUsageLog
from app.utils.audit_logger import log_ai_call
logger = logging.getLogger(__name__)


# Token pricing (as of Oct 2026, in dollars per 1M tokens)
# Update these as providers change pricing
TOKEN_PRICING = {
    # Claude
    'claude-sonnet-5': {'input': 2.00, 'output': 10.00},
    'claude-opus-5': {'input': 5.00, 'output': 25.00},
    # Gemini
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50},
    'gemini-2.5-pro': {'input': 1.25, 'output': 10.00},
    'gemini-4-argon': {'input': 4.00, 'output': 20.00},
    'gemini-3.8-flash': {'input': 0.75, 'output': 3.75},
    'gemini-3.6-flash': {'input': 0.75, 'output': 3.75},
    'gemini-3.5-flash-lite': {'input': 0.30, 'output': 2.50},
    'gemini-3-flash-preview': {'input': 0.50, 'output': 3.00},
    'gemini-3.1-pro-preview': {'input': 2.00, 'output': 12.00},
    # DeepSeek
    'deepseek-flash': {'input': 0.30, 'output': 1.20},      # V4 Flash (peak)
    'deepseek-v4-pro': {'input': 1.32, 'output': 3.96},     # V4 Pro (peak)
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
        model: Specific model used (e.g., 'claude-sonnet-5')
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

        # GDPR audit trail
        log_ai_call(
            user_id=user_id,
            provider=provider,
            model=model,
            task_type=prompt_name,
            tokens_used=total_tokens,
            success=success,
        )

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
        pricing = TOKEN_PRICING['claude-sonnet-5']

    # Calculate cost per million tokens, convert to cents
    input_cost = (input_tokens or 0) * pricing['input'] / 1_000_000
    output_cost = (output_tokens or 0) * pricing['output'] / 1_000_000

    total_cost_dollars = input_cost + output_cost
    total_cost_cents = int(total_cost_dollars * 100)

    return total_cost_cents


def _group_by(logs, field):
    """Group logs by a field and count"""
    groups = {}
    for log in logs:
        key = getattr(log, field, 'unknown')
        if key not in groups:
            groups[key] = 0
        groups[key] += 1
    return groups
