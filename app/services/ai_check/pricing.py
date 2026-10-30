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

"""Dollar estimate for one API response.

Token prices come from genai-prices (Pydantic's maintained price data), as bundled in the pinned
version: no runtime fetching. Dependabot opens a monthly PR to bump the pin (.github/dependabot.yml),
which is how prices get updated. The library applies tiered context
pricing and DeepSeek's peak/off-peak rates from the response time. Web search is priced here per
query, since genai-prices does not cover it. Models genai-prices doesn't know fall back to
FALLBACK_PRICES, priced at the most expensive model of the same provider."""

from genai_prices import Usage as PriceUsage
from genai_prices import calc_price

from app.utils.time_utils import now_utc

PROVIDER_IDS = {'claude': 'anthropic', 'gemini': 'google', 'deepseek': 'deepseek'}
# Our model id -> genai-prices' id for the same model and price.
MODEL_ALIASES = {'deepseek-flash': 'deepseek-v4-flash'}
# Per web search query (provider list prices; Gemini's free monthly allowance is ignored).
SEARCH_PRICES = {'claude': 0.010, 'gemini': 0.014, 'deepseek': 0.0}
DEFAULT_SEARCH_PRICE = 0.014

# Fallback only: models genai-prices does not know. Per million tokens; DeepSeek at peak rates.
FALLBACK_PRICES = {
    'claude-opus-5': {'in': 5.00, 'out': 25.00, 'cached_in': 0.50},
    'claude-sonnet-5': {'in': 2.00, 'out': 10.00, 'cached_in': 0.20},
    # genai-prices 0.1.11 lacks it; Dec 1 2026 list price (intro $2/$10 ends Nov 30)
    'gemini-4-argon': {'in': 4.00, 'out': 20.00, 'cached_in': 0.20},
    'gemini-3-flash-preview': {'in': 0.50, 'out': 3.00, 'cached_in': 0.05},
    'gemini-3.1-pro-preview': {'in': 2.00, 'out': 12.00, 'cached_in': 0.20,
                               'long_in': 4.00, 'long_out': 18.00, 'long_cached_in': 0.40},
    'gemini-2.5-flash': {'in': 0.30, 'out': 2.50, 'cached_in': 0.03},
    'gemini-2.5-pro': {'in': 1.25, 'out': 10.00, 'cached_in': 0.125,
                       'long_in': 2.50, 'long_out': 15.00, 'long_cached_in': 0.25},
    'deepseek-flash': {'in': 0.30, 'out': 1.20, 'cached_in': 0.006},
    'deepseek-v4-pro': {'in': 1.32, 'out': 3.96, 'cached_in': 0.044},
}
LONG_CONTEXT_TOKENS = 200_000
CACHE_WRITE_MULTIPLIER = 1.25
DEFAULT_PRICE_MODEL = 'claude-opus-5'  # a model from no known provider: price conservatively


def provider_of(model_id):
    for provider in ('claude', 'gemini', 'deepseek'):
        if (model_id or '').startswith(provider):
            return provider
    return ''


def _fallback_price(model_id):
    if model_id in FALLBACK_PRICES:
        return FALLBACK_PRICES[model_id]
    provider = provider_of(model_id)
    same = [price for model, price in FALLBACK_PRICES.items() if provider and provider_of(model) == provider]
    return max(same, key=lambda price: price['out']) if same else FALLBACK_PRICES[DEFAULT_PRICE_MODEL]


def _fallback_token_cost(usage):
    price = _fallback_price(usage.model)
    prompt_tokens = usage.tokens_in + usage.cached_in + usage.cache_write
    prefix = 'long_' if 'long_in' in price and prompt_tokens > LONG_CONTEXT_TOKENS else ''
    rate_in = price[prefix + 'in']
    return (
        usage.tokens_in * rate_in
        + usage.cached_in * price[prefix + 'cached_in']
        + usage.cache_write * rate_in * CACHE_WRITE_MULTIPLIER
        + usage.tokens_out * price[prefix + 'out']
    ) / 1_000_000


def _token_cost(usage, at):
    price_usage = PriceUsage(
        input_tokens=usage.tokens_in + usage.cached_in + usage.cache_write,  # genai-prices wants the total
        cache_read_tokens=usage.cached_in, cache_write_tokens=usage.cache_write,
        output_tokens=usage.tokens_out)
    try:
        result = calc_price(price_usage, model_ref=MODEL_ALIASES.get(usage.model, usage.model),
                            provider_id=PROVIDER_IDS.get(provider_of(usage.model)),
                            genai_request_timestamp=at or now_utc())
    except LookupError:
        return _fallback_token_cost(usage)
    return float(result.total_price)


def estimate_cost(usage, at=None):
    """Dollars for one response. `at` is when it was answered (default now): DeepSeek's rate
    depends on the hour."""
    search_price = SEARCH_PRICES.get(provider_of(usage.model), DEFAULT_SEARCH_PRICE)
    return _token_cost(usage, at) + usage.searches * search_price
