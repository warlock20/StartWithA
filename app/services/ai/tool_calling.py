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
Provider-agnostic tool-calling primitives.

The types here describe an agentic tool-calling conversation in a neutral shape,
independent of any provider SDK. Providers translate to/from their own formats
(Gemini FunctionDeclaration, Claude tool_use blocks); the orchestration loop
(`run_tool_loop`, added in Task 4) drives the conversation using only these types.

- ToolSpec:   the menu entry the model sees (name + description + JSON-Schema params)
- ToolCall:   the model's request to run a tool
- ToolResult: the executed result fed back to the model
- TurnResult: one model turn — either prose text, or tool-call requests
- ToolLoopResult: the final outcome of the whole loop
"""

import logging

from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Appended to the transcript before the forced final turn. Dropping the tool menu
# is not enough on its own: a transcript full of tool calls keeps the model
# emitting more of them, so the instruction has to be stated in-band.
_FINAL_TURN_INSTRUCTION = (
    "You have used all available tool calls and no tools remain. Do not request "
    "another tool. Answer now in prose using only what the tool results above "
    "already gave you, and say plainly which parts you could not determine."
)

# Last-resort user-facing text, so an empty model turn never surfaces as a blank
# answer that the caller reports as success.
_EMPTY_ANSWER_FALLBACK = (
    "I couldn't assemble an answer from your data for that question. "
    "Try narrowing it or asking about one holding at a time."
)


@dataclass
class ToolSpec:
    """A tool the model may call. `parameters` is a JSON-Schema object."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCall:
    """A model's request to invoke a tool.

    `signature` is an opaque, provider-specific token that some models (e.g.
    Gemini 3's `thought_signature`) attach to a function call and REQUIRE to be
    echoed back when the call is replayed into the next turn's history. Providers
    populate it on extraction and restore it when rebuilding the transcript;
    providers that don't use it leave it None.
    """
    id: str
    name: str
    arguments: Dict[str, Any]
    signature: Optional[Any] = None


@dataclass
class ToolResult:
    """The result of executing a ToolCall, fed back to the model."""
    id: str
    content: str


@dataclass
class Message:
    """
    One entry in the neutral transcript every provider must speak.

    This is the provider-agnostic contract: `run_tool_loop` and callers build
    `Message`s (or plain dicts, coerced at the boundary), and each provider's
    `generate_turn` translates them into its own SDK format.

    - role 'user'      → content
    - role 'assistant' → content and/or tool_calls (a model turn)
    - role 'tool'      → content is a tool result, tool_call_id correlates it
    """
    role: str
    content: str = ''
    tool_calls: List["ToolCall"] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    raw: Any = None
    """The provider's own rendering of a model turn, opaque to this module.

    Rebuilding a model turn from its ToolCalls loses whatever else the provider
    put in it. Gemini's grounded turns carry extra parts alongside the function
    call, each with a thought_signature, and it rejects the next request unless
    the turn is replayed exactly as sent. Providers that need this store the
    turn here and replay it; the rest leave it None.
    """

    @classmethod
    def coerce(cls, m: Any) -> "Message":
        """Accept an existing Message or a plain dict; return a Message."""
        if isinstance(m, cls):
            return m
        return cls(
            role=m.get('role', 'user'),
            content=m.get('content', '') or '',
            tool_calls=m.get('tool_calls', []) or [],
            tool_call_id=m.get('tool_call_id'),
            raw=m.get('raw'),
        )


# An executor takes a ToolCall and returns its ToolResult.
ToolExecutorFn = Callable[[ToolCall], ToolResult]


@dataclass
class ToolLoopResult:
    """Final outcome of an agentic tool-calling loop."""
    text: str
    hops: int
    calls: List[ToolCall] = field(default_factory=list)


@dataclass
class TurnResult:
    """One model turn: either prose `text`, or `tool_calls` requesting execution."""
    text: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None
    """The provider's own turn object, for verbatim replay. See Message.raw."""


def run_tool_loop(provider, messages, tools, executor,
                  system=None, max_hops=5, max_tokens=1024, temperature=0.3,
                  google_search: bool = False) -> ToolLoopResult:
    """
    Drive an agentic tool-calling conversation.

    The provider owns ONE turn (`generate_turn`); this function owns the loop:
    ask the model with the tool menu; if it returns tool calls, execute them,
    append the results to the transcript, and ask again; stop when the model
    returns prose, or when the hop cap is reached (then force a final,
    tool-free answer so the user always gets prose back).

    Args:
        provider:    object with `generate_turn(messages, tools, system, max_tokens, temperature)`
        messages:    neutral transcript — list of dicts with 'role' and 'content';
                     assistant tool requests carry 'tool_calls', tool results carry 'tool_call_id'
        tools:       list[ToolSpec] the model may call
        executor:    ToolExecutorFn mapping a ToolCall to a ToolResult
        system:      optional system prompt
        max_hops:    maximum tool-execution rounds before forcing an answer
        google_search: ground every turn on Google's built-in search alongside `tools`
    """
    transcript: List[Message] = [Message.coerce(m) for m in messages]
    all_calls: List[ToolCall] = []
    hops = 0
    while True:
        turn = provider.generate_turn(transcript, tools, system=system,
                                      max_tokens=max_tokens, temperature=temperature,
                                      google_search=google_search)

        # Model wants to call tools and we still have budget: execute + continue.
        if turn.tool_calls and hops < max_hops:
            hops += 1
            transcript.append(Message(role='assistant', content=turn.text or '',
                                      tool_calls=turn.tool_calls, raw=turn.raw))
            for call in turn.tool_calls:
                all_calls.append(call)
                res = executor(call)
                transcript.append(Message(role='tool', tool_call_id=call.id,
                                          content=res.content))
            continue

        # Hop cap hit while the model still wants tools: force a tool-free answer.
        if turn.tool_calls and hops >= max_hops:
            logger.info(
                f"tool loop hit the {max_hops}-hop cap "
                f"(last request: {', '.join(c.name for c in turn.tool_calls)}); "
                "forcing a final answer")
            transcript.append(Message(role='user', content=_FINAL_TURN_INSTRUCTION))
            final = provider.generate_turn(transcript, [], system=system,
                                           max_tokens=max_tokens, temperature=temperature,
                                           google_search=google_search)
            return ToolLoopResult(text=_answer_text(final), hops=hops, calls=all_calls)

        # Model returned prose: done.
        return ToolLoopResult(text=_answer_text(turn), hops=hops, calls=all_calls)


def _answer_text(turn: TurnResult) -> str:
    """The turn's prose, or a stated fallback — never a silent empty string.

    A turn can carry no text at all (the model spent the turn on a tool request,
    or ran the output budget down on reasoning), and returning '' from here shows
    up as a blank answer that the caller still reports as a success.
    """
    text = (turn.text or '').strip()
    if text:
        return text
    logger.warning(
        "model turn produced no text "
        f"(tool_calls={[c.name for c in turn.tool_calls]}); returning fallback")
    return _EMPTY_ANSWER_FALLBACK
