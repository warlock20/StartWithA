---
name: updating-ai-models
description: Use when adding, retiring, renaming or repricing an LLM model (Gemini, Claude, DeepSeek) in this app; when a provider announces a new model, deprecation, shutdown or price change; or when cleaning up stale model ids, labels or pricing entries.
---

# Updating AI models

## Overview

A model id is registered in about a dozen places, and nothing ties them together. A model missing from one of them fails silently:
- `AIModel.from_string` falls back to the default Flash model.
- AI check refuses the model, or prices it at the most expensive model of the same provider.
- Labels show the raw id.

Work through the registry below on every change.

## 1. Get facts from the provider, not memory

- Gemini: `ai.google.dev/gemini-api/docs/` `models/<id>`, `deprecations`, `pricing`, `changelog`
- Claude: the models overview and deprecations pages on docs.claude.com
- DeepSeek: `api-docs.deepseek.com`

For each model, record:
- the exact id, and whether it's stable or preview
- the shutdown date (deprecated is not the same as shut down)
- in, out and cached prices, plus any dated price change
- request rules: the thinking parameter, the minimum `max_output_tokens`, and ignored or rejected parameters
- whether web search and function tools work in one request

Check whether genai-prices (the pinned version in `requirements.txt`) knows the model:

```bash
venv/bin/python -I -c "from genai_prices import calc_price, Usage; print(calc_price(Usage(input_tokens=10**6, output_tokens=10**6), model_ref='MODEL_ID', provider_id='google').total_price)"
```

Use `provider_id` `google`, `anthropic` or `deepseek`. A `LookupError` means the model needs a `FALLBACK_PRICES` entry.

## 2. Registry

| # | Where | On add | On shutdown |
|---|---|---|---|
| 1 | `app/services/ai/config.py`: `AIModel` enum and the `from_string` map | Add the member and the map entry | Remove the member. Map the old id to its replacement with a "Retired by the API" comment, so saved prefs and env values still resolve |
| 2 | Defaults: in `config.py`, the `AIConfig` fields, the `from_env` getenv defaults, the unknown-name fallback and the module docstring. Also the `GeminiProvider` fallback in `providers/gemini.py` and the docstring in `app/services/ai/__init__.py` | Change only if the user chose a new default. It's a cost decision, so ask | Repoint if the default model is the one retired |
| 3 | `prompt_service._MODEL_DISPLAY_NAMES` | Add a label | Remove |
| 4 | `app/settings/ai_model_routes._get_available_models` (settings picker) | Add | Remove |
| 5 | `app/services/ai/prompts/ai_routing.yaml` `available_models` | Add | Remove |
| 6 | Prompt YAMLs with a concrete `model:` (`grep -rn '^model:' app/services/ai/prompts`) | — | Repoint them |
| 7 | `app/services/ai/analytics.py` `TOKEN_PRICING` (no dates; unknown ids price as Sonnet 4) | Add the price | Remove |
| 8 | `app/services/ai_check/setup.py`: `_SEARCHERS` (search plus tools in one call) or `_READERS`, `TEXT_ONLY`, `MODEL_LABELS`, `STAGE_RULES` wording | Add to the right list | Remove, and add `old id → replacement` to `_ALIASES`. `canonical()` doesn't use `from_string`, so without the alias saved `ai_check:<stage>` prefs fail `check_stage_model` |
| 9 | `app/services/ai/prompts/research/ai_check_presets.yaml` | Each value must be in that stage's list | Repoint |
| 10 | `app/services/ai_check/pricing.py` `FALLBACK_PRICES` and `MODEL_ALIASES` | Only if genai-prices lacks the model. A pricier entry raises the unknown-model price for that provider, so update the pricing test | Remove |
| 11 | Gemini request rules: the `gemini_output_tokens` prefix in `providers/gemini.py` and the thinking-level prefix tuple in `ai_check/adapters/gemini.py` | Extend both to cover a new generation | — |

Claude and DeepSeek: read the provider's migration notes for request-shape changes. The Claude adapter sends `effort`.

## 3. Deprecated, shut down, or dead

- **Deprecated but still served:** keep it in every list above, including pricing. Optionally relabel it "(Legacy)" or "(retires YYYY-MM-DD)" in all three label maps (3, 4 and 8). Removing its price early makes cost estimates use the wrong rate.
- **Shut down:** apply the "On shutdown" column.
- **Dead entry:** delete it. An entry is dead when nothing can produce that id: it isn't in the enum, or `from_string` maps it to a different id. Usage logs record the resolved `model_id`.

## 4. Before finishing

- Run `grep -rn "OLD_OR_NEW_ID" app` to catch stragglers.
- The tests live in `unittests/`, which is git-ignored:
  - `test_gemini_models.py`
  - `test_gemini_provider.py`
  - `test_ai_check_{setup,pricing,gemini_adapter,pipeline,models}.py`
  - `test_ai_model_selection.py`

  Run `venv/bin/python -m pytest unittests/ -k "ai_check or gemini or ai_model or analytics" -q`.
- Tell the user about anything code can't cover:
  - Railway `AI_DEFAULT_MODEL`, `AI_QUALITY_MODEL` and `AI_FAST_MODEL` on both the web and worker services.
  - Slow thinking models against gunicorn's `--timeout 120` and the AI-check soft limits in `app/celery_tasks/tasks_ai_check.py`.
  - Scheduled price changes that `TOKEN_PRICING` won't follow.

## Common mistakes

- Taking ids or prices from memory or from the request without checking the provider's page.
- Registering the model in `from_string` but not in AI check's `setup.py`, or the other way round.
- Removing a deprecated model that is still being served.
- Retiring an id without adding it to both `from_string` and `setup._ALIASES`.
- Changing a default model without asking.
