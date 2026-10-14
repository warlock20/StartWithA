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

"""Provider-neutral calls for the AI check: request/response types, the tool-result loop, usage."""

from dataclasses import dataclass, field, replace
from typing import Optional

from app.services.ai.prompt_service import prompt_service
from app.services.ai_check import AICheckError
from app.services.ai_check.pricing import estimate_cost


@dataclass
class Document:
    """One source handed to the model. `page_texts` are PyMuPDF page texts (one entry for a text
    file), used for quote verification; `as_text` is the YAML-wrapped text for text-only input."""
    title: str
    kind: str  # 'pdf' or 'text'
    path: str
    page_texts: list
    as_text: str


@dataclass
class StageCall:
    model: str
    system: str
    text: str
    tools: list
    documents: list = field(default_factory=list)
    search_cap: Optional[int] = None  # set only for Gather: searches this call may run
    fetch_cap: Optional[int] = None  # set only when the model fetches a web page itself (Claude)
    max_tokens: int = 16000
    effort: str = 'medium'


@dataclass
class Usage:
    """One API response's usage. `tokens_in` is uncached, non-cache-write input only."""
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached_in: int = 0
    cache_write: int = 0
    searches: int = 0
    fetches: int = 0  # pages the provider fetched itself (Claude web_fetch)


@dataclass
class StageReply:
    tool_name: Optional[str]  # None when the model ended without calling a tool
    tool_input: dict
    transcript: object  # adapter-specific; passed back to follow_up for the reminder
    usages: list
    fetched_texts: list = field(default_factory=list)  # page text the provider fetched, for verification


@dataclass
class UsageTally:
    """Usage spent during one stage, kept off the ORM row until the pipeline applies it atomically."""
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    web_searches: int = 0
    web_fetches: int = 0
    cost_estimate: float = 0.0


def stage_call(data, model, text, tools, documents=(), search_cap=None, fetch_cap=None):
    """A StageCall for one stage, with system text, max_tokens and effort from its YAML data."""
    return StageCall(model=model, system=data.get('system_context') or '', text=text, tools=list(tools),
                     documents=list(documents), search_cap=search_cap, fetch_cap=fetch_cap,
                     max_tokens=data.get('max_tokens', 16000), effort=data.get('effort', 'medium'))


def call_for_tool(adapter, call, names, on_usage):
    """Run until the model calls one of `names`; one reminder if it doesn't.
    Returns (name, input, fetched_texts), the fetched texts of both attempts combined.
    The reminder's search cap is lowered by what the first attempt used, floor 1, so a run may
    exceed a stage's search cap by at most 1."""
    reply = adapter.send(call, on_usage)
    if reply.tool_name in names:
        return reply.tool_name, reply.tool_input, list(reply.fetched_texts)
    tool_names = ' or '.join(sorted(names))
    reminder = prompt_service.get_prompt('research', 'ai_check_tool_reminder', tool_names=tool_names)
    retry_call = call
    if call.search_cap is not None:
        used = sum(usage.searches for usage in reply.usages)
        retry_call = replace(call, search_cap=max(1, call.search_cap - used))
    fetched = list(reply.fetched_texts)
    reply = adapter.follow_up(retry_call, reply.transcript, reminder, on_usage)
    if reply.tool_name not in names:
        raise AICheckError(f'The model did not return a result through {tool_names}.')
    return reply.tool_name, reply.tool_input, fetched + list(reply.fetched_texts)


def record_usage(tally, usage):
    """Add one response's usage and cost to the tally (not committed)."""
    tally.tokens_in += usage.tokens_in + usage.cached_in + usage.cache_write
    tally.tokens_out += usage.tokens_out
    tally.cache_read_tokens += usage.cached_in
    tally.web_searches += usage.searches
    tally.web_fetches += usage.fetches
    tally.cost_estimate += estimate_cost(usage)
