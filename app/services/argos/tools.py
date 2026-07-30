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
Companion tools + the ownership-bound ToolExecutor.

`COMPANION_TOOLS` are the schemas the model sees (names, descriptions, JSON-Schema
params). `ToolExecutor` is the SECURITY BOUNDARY: it binds `current_user.id` at
construction and validates ownership of every company/project/resource id before
touching a service. The model never supplies a user id and cannot reach another
user's data — a bad id returns an error string, never a leak.

Each tool is a thin wrapper over a service we already have; results are returned
as compact JSON (dates/Decimals stringified) for the model to read.
"""

import json
import logging
import dataclasses

from app.services.ai.tool_calling import ToolSpec, ToolResult
from app.services.argos.core import ArgosService
from app.services.argos.knowledge_search import search_my_knowledge, get_resource
from app.services.portfolio_intelligence import PortfolioIntelligenceService
from app.models.company import Company
from app.models.research import ResearchProject
from app.models.journal import PatternRecognition
from app.models.idea_pipeline import MistakeLog

logger = logging.getLogger(__name__)


COMPANION_TOOLS = [
    ToolSpec(
        'get_portfolio_overview',
        "The user's portfolio: positions, weights, concentration, and how each "
        "holding's actual return compares to its original thesis.",
        {'type': 'object', 'properties': {}},
    ),
    ToolSpec(
        'get_company_context',
        "Everything the user knows about one company: research state, flags, thesis, "
        "past decision, held position, and their journal/mistake/pattern history for it.",
        {'type': 'object',
         'properties': {'company_id': {'type': 'integer'}},
         'required': ['company_id']},
    ),
    ToolSpec(
        'get_research_project',
        "Findings, questions, flags, and thesis for one research project.",
        {'type': 'object',
         'properties': {'project_id': {'type': 'integer'}},
         'required': ['project_id']},
    ),
    ToolSpec(
        'search_my_knowledge',
        "Semantic search across the user's own research findings, journal notes, "
        "saved links, decisions, and logged mistakes. Use for 'what did I find/note "
        "about X' questions. Optionally scope to one company.",
        {'type': 'object',
         'properties': {'query': {'type': 'string'},
                        'company_id': {'type': 'integer'}},
         'required': ['query']},
    ),
    ToolSpec(
        'get_resource',
        "Fetch the raw text of one note or saved resource returned by "
        "search_my_knowledge (source_type is 'journal' or 'resource').",
        {'type': 'object',
         'properties': {'source_type': {'type': 'string'},
                        'source_id': {'type': 'integer'}},
         'required': ['source_type', 'source_id']},
    ),
    ToolSpec(
        'get_mistakes_and_patterns',
        "The user's past mistakes and behavioural patterns, as facts to weigh against "
        "the current decision.",
        {'type': 'object',
         'properties': {'topic': {'type': 'string'}}},
    ),
]


class ToolExecutor:
    """Dispatches a ToolCall to its handler, scoped to one user."""

    def __init__(self, user_id):
        self.user_id = user_id

    def __call__(self, call):
        handler = getattr(self, f'_{call.name}', None)
        if handler is None:
            return ToolResult(call.id, f"Unknown tool: {call.name}")
        try:
            data = handler(call.arguments or {})
            return ToolResult(call.id, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"companion tool {call.name} failed: {e}")
            return ToolResult(call.id, json.dumps({'error': f'Tool failed: {e}'}))

    # --- handlers (each ownership-scoped to self.user_id) ----------------

    def _get_company_context(self, args):
        company = Company.query.filter_by(
            id=args.get('company_id'), user_id=self.user_id).first()
        if not company:
            return {'error': 'Company not found or access denied'}
        return ArgosService(self.user_id).build_company_context(company.id).to_summary()

    def _get_research_project(self, args):
        project = ResearchProject.query.filter_by(
            id=args.get('project_id'), user_id=self.user_id).first()
        if not project:
            return {'error': 'Project not found or access denied'}
        return ArgosService(self.user_id).build_research_context(project.id).to_dict()

    def _get_portfolio_overview(self, args):
        service = PortfolioIntelligenceService(self.user_id)
        reality = service.get_thesis_reality_check()
        return {
            'positions': [
                dataclasses.asdict(t) if dataclasses.is_dataclass(t) else dict(t.__dict__)
                for t in reality[:20]
            ],
        }

    def _search_my_knowledge(self, args):
        return {'results': search_my_knowledge(
            self.user_id, args['query'], args.get('company_id'))}

    def _get_resource(self, args):
        resource = get_resource(self.user_id, args['source_type'], args['source_id'])
        return resource or {'error': 'Not found or access denied'}

    def _get_mistakes_and_patterns(self, args):
        # User-wide mistakes + behavioural patterns (not company-scoped).
        mistakes = (MistakeLog.query
                    .filter_by(user_id=self.user_id)
                    .order_by(MistakeLog.id.desc()).limit(8).all())
        patterns = (PatternRecognition.query
                    .filter_by(user_id=self.user_id)
                    .order_by(PatternRecognition.impact_score.desc()).limit(5).all())
        return {
            'mistakes': [
                {'title': m.title, 'type': m.mistake_type, 'lesson': m.lesson_learned}
                for m in mistakes
            ],
            'patterns': [
                {'name': p.pattern_name, 'impact': p.impact_score,
                 'how_to_avoid': p.how_to_avoid}
                for p in patterns
            ],
        }
