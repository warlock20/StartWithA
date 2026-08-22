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

"""Model selection in AIService._get_provider.

Every prompt YAML carries both `preferred_provider` and `model`, and every call
site passes both. The provider branch short-circuited before the model was ever
read, so the requested model was silently dropped and every call in the app ran
on the configured default. The recorded model was the YAML's claim, not reality,
which made the stored `model` column and the cost analytics wrong.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai.ai_service import AIService
from app.services.ai.config import AIModel, AIProvider


def test_requested_model_is_honoured_when_provider_is_also_given(app_context):
    service = AIService()
    wanted = AIModel.from_string('gemini-3-pro-preview')

    provider = service._get_provider(provider=AIProvider.GEMINI, model=wanted)

    assert provider.model_name == wanted.model_id


def test_requested_model_is_honoured_without_a_provider(app_context):
    service = AIService()
    wanted = AIModel.from_string('gemini-3-pro-preview')

    provider = service._get_provider(model=wanted)

    assert provider.model_name == wanted.model_id


def test_falls_back_to_the_default_model_when_none_requested(app_context):
    service = AIService()

    provider = service._get_provider(provider=AIProvider.GEMINI)

    assert provider.model_name == service._config.default_model.model_id


def test_resolve_model_id_reports_what_would_actually_run(app_context):
    """The recorded model must come from the resolved provider, not the prompt
    YAML's request — those disagreed for every row already in the database."""
    service = AIService()
    wanted = AIModel.from_string('gemini-3-pro-preview')

    assert service.resolve_model_id(provider=AIProvider.GEMINI,
                                    model=wanted) == 'gemini-3.1-pro-preview'
    assert service.resolve_model_id(provider=AIProvider.GEMINI) == \
        service._config.default_model.model_id


def test_resolve_model_id_is_none_when_nothing_can_serve_it(app_context):
    service = AIService()
    claude = AIModel.from_string('claude-sonnet-4-20250514')

    # Claude is not configured here; recording a model that never ran is worse
    # than recording nothing.
    assert service.resolve_model_id(model=claude) is None
