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

"""Dollar estimate for one API response. Rates per million tokens (Anthropic list prices)."""

# model id -> (input $/MTok, output $/MTok)
PRICES = {
    'claude-opus-5': (5.00, 25.00),
    'claude-sonnet-5': (2.00, 10.00),
}
DEFAULT_PRICE_MODEL = 'claude-opus-5'  # fallback-served or unknown models: price conservatively
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25
WEB_SEARCH_PER_REQUEST = 10.00 / 1000  # verify against the current pricing page when tuning


def estimate_cost(model_id, usage):
    price_in, price_out = PRICES.get(model_id, PRICES[DEFAULT_PRICE_MODEL])
    per_token_in, per_token_out = price_in / 1_000_000, price_out / 1_000_000
    server = usage.get('server_tool_use') or {}
    return (
        (usage.get('input_tokens') or 0) * per_token_in
        + (usage.get('cache_read_input_tokens') or 0) * per_token_in * CACHE_READ_MULTIPLIER
        + (usage.get('cache_creation_input_tokens') or 0) * per_token_in * CACHE_WRITE_MULTIPLIER
        + (usage.get('output_tokens') or 0) * per_token_out
        + (server.get('web_search_requests') or 0) * WEB_SEARCH_PER_REQUEST
    )
