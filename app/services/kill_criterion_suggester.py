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
Suggest a kill checklist question that would have caught a logged mistake.

The AI proposes; nothing reaches a checklist until the user presses Add
(``add_suggested_criterion``). No ``KillChecklistSuggestion`` rows are created.
"""

import json

from app import db
from app.models.idea_pipeline import KillChecklist, KillCriterion, MistakeLog
from app.services.ai import generate_json
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.currency_service import CurrencyService

# Rough token budget a caller should check before running a suggestion.
KILL_CRITERION_TOKEN_ESTIMATE = 3000

QUESTION_MAX_LENGTH = 500
MAX_SUGGESTIONS = 3
THRESHOLD_TYPES = ('numerical', 'qualitative')
NOT_RECORDED = 'Not recorded'


class NoUsableSuggestion(Exception):
    """The model returned nothing usable and did not say the mistake is already covered."""


class DuplicateCriterion(Exception):
    """The checklist already has this question."""


class CriterionInUse(Exception):
    """The criterion has already been used in an evaluation and cannot be undone."""


def default_kill_checklist(user_id: int):
    """The user's default kill checklist, else their first by name, else None."""
    return (
        KillChecklist.query.filter_by(user_id=user_id)
        .order_by(KillChecklist.is_default.desc(), KillChecklist.name, KillChecklist.id)
        .first()
    )


def _text(value) -> str:
    if value is None:
        return NOT_RECORDED
    value = str(value).strip()
    return value or NOT_RECORDED


def _joined(items) -> str:
    if not items:
        return NOT_RECORDED
    if isinstance(items, str):
        return _text(items)
    parts = [str(i).strip() for i in items if str(i).strip()]
    return '; '.join(parts) if parts else NOT_RECORDED


def _format_cost(mistake: MistakeLog) -> str:
    if mistake.cost_estimate is None:
        return NOT_RECORDED
    currency = (mistake.user.base_currency if mistake.user else None) or 'USD'
    return f"{CurrencyService.get_currency_symbol(currency)}{mistake.cost_estimate:,.0f}"


def _numbered(criteria) -> str:
    if not criteria:
        return 'No criteria yet'
    return '\n'.join(f"{i}. {c.question}" for i, c in enumerate(criteria, start=1))


def _criterion_index(value, count):
    """0-based index for a 1-based criterion number (int or numeric string), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            return None
        value = int(value)
    if not isinstance(value, int):
        return None
    return value - 1 if 1 <= value <= count else None


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'yes', '1')
    return value is True


def _clean_suggestion(raw):
    if not isinstance(raw, dict):
        return None
    question = str(raw.get('question') or '').strip()[:QUESTION_MAX_LENGTH]
    if not question:
        return None
    try:
        confidence = min(1.0, max(0.0, float(raw.get('confidence'))))
    except (TypeError, ValueError):
        confidence = 0.5
    threshold = str(raw.get('threshold_type') or '').strip().lower()
    return {
        'question': question,
        'help_text': str(raw.get('help_text') or '').strip(),
        'failure_reason': str(raw.get('failure_reason') or '').strip(),
        'why_it_catches': str(raw.get('why_it_catches') or '').strip(),
        'threshold_type': threshold if threshold in THRESHOLD_TYPES else 'qualitative',
        'confidence': confidence,
    }


def suggest_kill_criteria(mistake: MistakeLog, checklist: KillChecklist) -> dict:
    """Ask the AI for 1-3 kill questions that would have caught ``mistake``."""
    criteria = checklist.criteria.all()
    prompt_data = prompt_service.get_prompt_with_metadata(
        'kill_checklist', 'mistake_analysis',
        mistake_title=_text(mistake.title),
        mistake_type=_text(mistake.mistake_type),
        mistake_severity=_text(mistake.severity),
        mistake_cost=_format_cost(mistake),
        mistake_date=mistake.occurred_date.strftime('%Y-%m-%d') if mistake.occurred_date else NOT_RECORDED,
        mistake_description=_text(mistake.description),
        root_cause=_text(mistake.root_cause),
        contributing_factors=_joined(mistake.contributing_factors),
        lesson_learned=_text(mistake.lesson_learned),
        prevention_steps=_joined(mistake.prevention_steps),
        process_changes=_text(mistake.process_changes),
        checklist_name=_text(checklist.name),
        existing_criteria=_numbered(criteria),
    )
    prompt = prompt_data['prompt']
    metadata = prompt_data.get('metadata', {})
    model_enum, provider_enum = resolve_model_provider(
        metadata, user_id=mistake.user_id, prompt_category='kill_checklist',
    )

    raw = generate_json(
        prompt,
        max_tokens=metadata.get('max_tokens'),
        temperature=metadata.get('temperature'),
        model=model_enum, provider=provider_enum,
    )
    tokens_used = len(prompt) // 4 + len(json.dumps(raw, default=str)) // 4
    if not isinstance(raw, dict):
        raise NoUsableSuggestion('The AI response was not a JSON object.')

    overlap = None
    raw_overlap = raw.get('overlap')
    if isinstance(raw_overlap, dict):
        idx = _criterion_index(raw_overlap.get('criterion_number'), len(criteria))
        if idx is not None:
            criterion = criteria[idx]
            overlap = {
                'criterion_id': criterion.id,
                'order': criterion.order,
                'position': idx + 1,
                'question': criterion.question,
                'explanation': str(raw_overlap.get('explanation') or '').strip(),
            }
    already_covered = _as_bool(raw.get('already_covered')) and overlap is not None

    raw_suggestions = raw.get('suggestions')
    if not isinstance(raw_suggestions, list):
        raw_suggestions = []
    suggestions = [s for s in (_clean_suggestion(r) for r in raw_suggestions) if s][:MAX_SUGGESTIONS]

    if not suggestions and not already_covered:
        raise NoUsableSuggestion('No usable kill criterion was suggested.')

    return {
        'suggestions': suggestions,
        'already_covered': already_covered,
        'overlap': overlap,
        'checklist': {'id': checklist.id, 'name': checklist.name},
        'tokens_used': tokens_used,
    }


def add_suggested_criterion(mistake: MistakeLog, checklist: KillChecklist, question: str,
                            help_text: str = '', failure_reason: str = '',
                            position: str = 'last') -> KillCriterion:
    """Add a suggested question to ``checklist`` (the user pressed Add)."""
    question = (question or '').strip()[:QUESTION_MAX_LENGTH]
    if not question:
        raise ValueError('Question is required.')

    existing = checklist.criteria.all()
    if any((c.question or '').strip().lower() == question.lower() for c in existing):
        raise DuplicateCriterion('This question is already on the checklist.')

    # Existing code numbers criteria from 0 (see app/ideas/routes.py), so an empty list starts at 0.
    orders = [c.order or 0 for c in existing]
    if position == 'first':
        new_order = min(orders) if orders else 0
        for criterion in existing:
            criterion.order = (criterion.order or 0) + 1
    else:
        new_order = max(orders) + 1 if orders else 0

    criterion = KillCriterion(
        kill_checklist_id=checklist.id,
        question=question,
        help_text=(help_text or '').strip(),
        failure_reason=(failure_reason or '').strip(),
        order=new_order,
        auto_suggested=True,
        source_mistake_id=mistake.id,
    )
    db.session.add(criterion)
    db.session.commit()
    return criterion


def undo_suggested_criterion(mistake: MistakeLog, criterion: KillCriterion) -> None:
    """Remove a criterion that was added from ``mistake`` and has not been used yet."""
    if criterion.source_mistake_id != mistake.id:
        raise ValueError('This criterion was not added from this mistake.')
    if (criterion.times_evaluated or 0) > 0:
        raise CriterionInUse('This criterion has already been used in an evaluation.')
    db.session.delete(criterion)
    db.session.commit()


def mistake_ids_with_criteria(user_id: int) -> set:
    """Ids of the user's mistakes that already have a criterion on one of their checklists."""
    rows = (
        db.session.query(KillCriterion.source_mistake_id)
        .join(KillChecklist, KillCriterion.kill_checklist_id == KillChecklist.id)
        .filter(KillChecklist.user_id == user_id, KillCriterion.source_mistake_id.isnot(None))
        .distinct()
        .all()
    )
    return {r[0] for r in rows}
