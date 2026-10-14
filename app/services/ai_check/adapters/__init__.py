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

"""One adapter per provider; stages talk to whichever one runs their model."""

from app.services.ai_check import AICheckError
from app.services.ai_check.adapters.claude import ClaudeAdapter
from app.services.ai_check.adapters.deepseek import DeepSeekAdapter
from app.services.ai_check.adapters.gemini import GeminiAdapter
from app.services.ai_check.pricing import provider_of

ADAPTERS = {'claude': ClaudeAdapter, 'gemini': GeminiAdapter, 'deepseek': DeepSeekAdapter}


def get_adapter(model_id):
    adapter_class = ADAPTERS.get(provider_of(model_id))
    if adapter_class is None:
        raise AICheckError(f'No AI check adapter for {model_id}.')
    return adapter_class()
