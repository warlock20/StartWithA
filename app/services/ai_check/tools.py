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

"""Strict tool schemas Claude uses to hand results back to the AI check pipeline."""


def _strict(name, description, properties, required):
    return {
        'name': name,
        'description': description,
        'strict': True,
        'input_schema': {'type': 'object', 'properties': properties, 'required': required,
                         'additionalProperties': False},
    }


_SOURCE_ITEM = {
    'type': 'object',
    'properties': {
        'url': {'type': 'string', 'description': 'Direct URL of the filing or page'},
        'title': {'type': 'string'},
        'doc_type': {'type': 'string', 'description': 'e.g. 10-K, 20-F, results release'},
        'period': {'type': 'string', 'description': 'e.g. FY2025'},
        'gap_filled': {'type': 'string', 'description': 'Which missing figure this source provides'},
    },
    'required': ['url', 'title', 'doc_type', 'period', 'gap_filled'],
    'additionalProperties': False,
}

RECORD_SOURCES_TOOL = _strict(
    'record_sources', 'Record the sources to read for this question.',
    {'sources': {'type': 'array', 'items': _SOURCE_ITEM}}, ['sources'])

_EVIDENCE_ITEM = {
    'type': 'object',
    'properties': {
        'metric': {'type': 'string'},
        'value': {'type': 'string', 'description': 'As it should be shown, e.g. $18.40B'},
        'value_numeric': {'type': ['number', 'null'], 'description': 'In units of `unit`'},
        'unit': {'type': 'string', 'description': 'e.g. USD millions, shares millions'},
        'period': {'type': 'string'},
        'location': {'type': 'string', 'description': 'Page number or section'},
        'quote': {'type': 'string', 'description': 'Exact text from the source containing the figure'},
    },
    'required': ['metric', 'value', 'value_numeric', 'unit', 'period', 'location', 'quote'],
    'additionalProperties': False,
}

RECORD_EVIDENCE_TOOL = _strict(
    'record_evidence', 'Record every figure from this source that the question needs.',
    {'items': {'type': 'array', 'items': _EVIDENCE_ITEM}}, ['items'])

_CALC_LINE = {
    'type': 'object',
    'properties': {
        'label': {'type': 'string'},
        'value': {'type': 'string'},
        'evidence': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Evidence labels, e.g. E2'},
        'note': {'type': ['string', 'null'], 'description': 'Formula or working, if any'},
        'kind': {'type': 'string', 'enum': ['line', 'total', 'comparison', 'context']},
    },
    'required': ['label', 'value', 'evidence', 'note', 'kind'],
    'additionalProperties': False,
}

SUBMIT_AI_CHECK_TOOL = _strict(
    'submit_ai_check', 'Submit the finished analysis.',
    {
        'summary': {'type': 'string'},
        'calculation': {'type': 'array', 'items': _CALC_LINE},
        'suggested_verdict': {'type': 'string',
                              'enum': ['satisfied', 'not_satisfied', 'needs_attention']},
        'verdict_reason': {'type': 'string', 'description': 'Quote the rubric line it matched'},
        'gaps': {'type': 'array', 'items': {'type': 'string'}},
    },
    ['summary', 'calculation', 'suggested_verdict', 'verdict_reason', 'gaps'])

REQUEST_MORE_EVIDENCE_TOOL = _strict(
    'request_more_evidence', 'Ask for one more round of sources for the listed missing figures.',
    {'gaps': {'type': 'array', 'items': {'type': 'string'}}}, ['gaps'])
