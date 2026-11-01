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
Context for each piece of a knowledge item, embedded together with the piece.

A piece cut from a long note loses what the note was about ("margins rose to
61%" — of which company?). Each piece therefore gets a short context:

- LLMContextualizer (default): a cheap model writes 1–2 sentences placing the
  piece in its note (contextual retrieval). Prompt: companion/chunk_context.
- PrefixContextualizer (fallback, free): "<company> — <title>:".

The prefix is used when the user opted out, is out of AI token budget, or the
LLM call fails. Each chunk records which one made its context, so the nightly
job can upgrade prefix rows later or downgrade them after an opt-out.
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider

logger = logging.getLogger(__name__)

LLM = 'llm'
PREFIX = 'prefix'

# Tokens a user must have left for a run to use the LLM contextualizer.
CONTEXT_BUDGET_TOKENS = 2000

# Note text sent with each piece. The note goes first in the prompt and only the
# piece changes, so a note's pieces share a prompt prefix the provider can cache.
DOC_CHAR_LIMIT = 6000

SOURCE_LABELS = {
    'journal': 'Journal note',
    'decision': 'Investment decision',
    'mistake': 'Logged mistake',
    'resource': 'Saved resource',
}


class ContextUnavailable(Exception):
    """The LLM could not write a context; the caller falls back to the prefix."""


@dataclass(frozen=True)
class SourceDoc:
    """One knowledge item, as plain text, ready to split and contextualize."""
    source_type: str
    source_id: int
    company_id: Optional[int]
    company_name: Optional[str]
    title: str
    text: str

    @property
    def label(self):
        return SOURCE_LABELS.get(self.source_type, self.source_type)

    @property
    def content_hash(self):
        """sha256 of title and text: unchanged hash means unchanged chunks."""
        return hashlib.sha256(f'{self.title}\n{self.text}'.encode('utf-8')).hexdigest()


class PrefixContextualizer:
    method = PREFIX

    def contextualize(self, doc, pieces):
        title = doc.title or doc.label
        prefix = f'{doc.company_name} — {title}:' if doc.company_name else f'{title}:'
        return [prefix] * len(pieces)


class LLMContextualizer:
    """One fast-model call per piece. Counts the tokens it uses, for the user's budget."""
    method = LLM

    def __init__(self, user_id):
        self.user_id = user_id
        self.tokens_used = 0

    def contextualize(self, doc, pieces):
        try:
            return [self._context(doc, piece) for piece in pieces]
        except ContextUnavailable:
            raise
        except Exception as e:
            raise ContextUnavailable(str(e)) from e

    def _context(self, doc, piece):
        prompt_data = prompt_service.get_prompt_with_metadata(
            'companion', 'chunk_context',
            source_label=doc.label, company=doc.company_name or 'none', title=doc.title or doc.label,
            document=doc.text[:DOC_CHAR_LIMIT], piece=piece)
        metadata = prompt_data['metadata']
        model_enum, provider_enum = resolve_model_provider(
            metadata, user_id=self.user_id, prompt_category='companion')
        answer = ai_service.generate_text(
            prompt_data['prompt'], model=model_enum, provider=provider_enum,
            max_tokens=metadata['max_tokens'], temperature=metadata['temperature'])
        answer = (answer or '').strip()
        self.tokens_used += (len(prompt_data['prompt']) + len(answer)) // 4
        if not answer:
            raise ContextUnavailable('empty answer')
        return answer


def wanted_method(user):
    """The context method this user should get now: 'llm', or 'prefix' when opted out or out of budget."""
    if not user.knowledge_context_enabled:
        return PREFIX
    if not user.can_use_ai_tokens(CONTEXT_BUDGET_TOKENS):
        return PREFIX
    return LLM


def contextualize(doc, pieces, llm=None):
    """Contexts for a doc's pieces and how they were made: (contexts, 'llm' | 'prefix').

    Pass llm=None for the prefix. An LLM failure falls back to the prefix.
    """
    if llm is not None:
        try:
            return llm.contextualize(doc, pieces), LLM
        except ContextUnavailable as e:
            logger.warning(f"knowledge context fell back to prefix ({doc.source_type} #{doc.source_id}): {e}")
    return PrefixContextualizer().contextualize(doc, pieces), PREFIX
