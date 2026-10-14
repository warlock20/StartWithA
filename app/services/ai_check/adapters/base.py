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

"""The shared shape of a provider adapter: capabilities, lazy client, send and follow_up."""

from abc import ABC, abstractmethod

from app.services.ai_check import AICheckError


class ProviderAdapter(ABC):
    """Translates neutral StageCalls into one provider's API and back.

    A subclass declares what the provider can do and implements four hooks; the base turns
    those into `send` (first attempt) and `follow_up` (the reminder after a turn with no tool call).
    """
    provider = ''  # pricing/provider key: 'claude', 'gemini', 'deepseek'
    name = ''  # shown in user-facing errors
    can_search = False  # web search inside the call (Gather, Quick)
    can_fetch = False  # the model fetches a web page itself (Claude web_fetch)

    def __init__(self, client=None):
        """`client` is the provider SDK client (or callable); tests inject a scripted one."""
        self._client = client

    def client(self):
        if self._client is None:
            self._client = self._make_client()
            if self._client is None:
                raise AICheckError(f'{self.name} is not configured on the server.')
        return self._client

    def send(self, call, on_usage):
        self._check_capabilities(call)
        return self._complete(call, self._first_turn(call), on_usage)

    def _check_capabilities(self, call):
        if call.search_cap is not None and not self.can_search:
            raise AICheckError(f"{self.name} can't search the web.")
        if call.fetch_cap is not None and not self.can_fetch:
            raise AICheckError(f"{self.name} can't fetch web pages itself; attach the downloaded page.")

    def follow_up(self, call, transcript, text, on_usage):
        return self._complete(call, self._append_user(transcript, text), on_usage)

    @abstractmethod
    def _make_client(self):
        """The SDK client, or None when the provider's key is not configured."""

    @abstractmethod
    def _first_turn(self, call):
        """The provider-shaped transcript for the call's first request (documents + text)."""

    @abstractmethod
    def _append_user(self, transcript, text):
        """The transcript with one more user turn (the reminder)."""

    @abstractmethod
    def _complete(self, call, transcript, on_usage):
        """Send the transcript, report usage, map stop reasons, return a StageReply."""
