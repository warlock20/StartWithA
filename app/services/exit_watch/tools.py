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

"""Strict tool schemas the exit-criteria check hands to the model."""
from app.services.ai_check.tools import strict_tool

RECORD_EXIT_CHECK_TOOL = strict_tool(
    'record_exit_check', 'Record where the exit rule stands now.',
    {
        'status': {'type': 'string', 'enum': ['intact', 'at_risk', 'triggered']},
        'changed': {'type': 'boolean',
                    'description': 'Does this check change the previous status?'},
        'summary': {'type': 'string'},
        'web_sources': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'source_id': {'type': 'string', 'description': 'A listed source id, e.g. S1'},
                    'published': {'type': ['string', 'null'],
                                  'description': 'Publication date of the source, if known'},
                },
                'required': ['source_id', 'published'],
                'additionalProperties': False,
            },
        },
        'app_figures': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'An app figure id, e.g. A1'},
                    'value': {'type': 'number', 'description': 'The figure value as listed'},
                },
                'required': ['id', 'value'],
                'additionalProperties': False,
            },
        },
    },
    ['status', 'changed', 'summary', 'web_sources', 'app_figures'])

REQUEST_SEARCH_TOOL = strict_tool(
    'request_search', 'Ask for a web search when the app figures cannot settle this rule.',
    {'query': {'type': 'string', 'description': 'One focused web search query'}}, ['query'])
