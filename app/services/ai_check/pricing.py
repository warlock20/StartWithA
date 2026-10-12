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

"""Dollar estimate for one API response. Rates per million tokens; `search` is per query."""

# Re-checked against the providers' pricing pages on 2026-10-12. DeepSeek: peak rates.
PRICES = {
    'claude-opus-5': {'in': 5.00, 'out': 25.00, 'cached_in': 0.50, 'search': 0.010},
    'claude-sonnet-5': {'in': 2.00, 'out': 10.00, 'cached_in': 0.20, 'search': 0.010},
    'gemini-3-flash-preview': {'in': 0.50, 'out': 3.00, 'cached_in': 0.05, 'search': 0.014},
    'gemini-3.1-pro-preview': {'in': 2.00, 'out': 12.00, 'cached_in': 0.20, 'search': 0.014,
                               'long_in': 4.00, 'long_out': 18.00, 'long_cached_in': 0.40},
    'gemini-2.5-flash': {'in': 0.30, 'out': 2.50, 'cached_in': 0.03, 'search': 0.035},
    'gemini-2.5-pro': {'in': 1.25, 'out': 10.00, 'cached_in': 0.125, 'search': 0.035,
                       'long_in': 2.50, 'long_out': 15.00, 'long_cached_in': 0.25},
    'deepseek-flash': {'in': 0.30, 'out': 1.20, 'cached_in': 0.006, 'search': 0.0},
    'deepseek-v4-pro': {'in': 1.32, 'out': 3.96, 'cached_in': 0.044, 'search': 0.0},
}
LONG_CONTEXT_TOKENS = 200_000
CACHE_WRITE_MULTIPLIER = 1.25
DEFAULT_PRICE_MODEL = 'claude-opus-5'  # a model from no known provider: price conservatively


def provider_of(model_id):
    for provider in ('claude', 'gemini', 'deepseek'):
        if (model_id or '').startswith(provider):
            return provider
    return ''


def _price(model_id):
    if model_id in PRICES:
        return PRICES[model_id]
    provider = provider_of(model_id)
    same = [price for model, price in PRICES.items() if provider and provider_of(model) == provider]
    return max(same, key=lambda price: price['out']) if same else PRICES[DEFAULT_PRICE_MODEL]


def estimate_cost(usage):
    price = _price(usage.model)
    prompt_tokens = usage.tokens_in + usage.cached_in + usage.cache_write
    prefix = 'long_' if 'long_in' in price and prompt_tokens > LONG_CONTEXT_TOKENS else ''
    rate_in, rate_out = price[prefix + 'in'], price[prefix + 'out']
    return (
        usage.tokens_in * rate_in
        + usage.cached_in * price[prefix + 'cached_in']
        + usage.cache_write * rate_in * CACHE_WRITE_MULTIPLIER
        + usage.tokens_out * rate_out
    ) / 1_000_000 + usage.searches * price['search']
