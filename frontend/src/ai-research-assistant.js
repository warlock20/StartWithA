import { mountIsland } from './lib/mountIsland';
import { AIAssistant } from './components/ai/AIAssistant';

/**
 * AI Research Assistant — React island entry.
 *
 * Exposes `window.initAIAssistant(elementId, config)` for template initialization.
 *
 * The component exposes `window.aiAssistant` on mount with:
 *   - updateContext(data)  — for AJAX navigation context updates
 *   - triggerMode(mode)    — programmatic mode trigger
 *   - formatResponse(text) — shared text formatter
 *   - context              — current context object
 *
 * NOTE: The old `app/static/js/ai-research-assistant.js` (class-based) stays loaded
 * on `free_research_step.html` and `company_detail.html` for backward compat.
 * This entry file is only used on `research_step.html`.
 */
window.initAIAssistant = function (elementId, config) {
  return mountIsland(elementId, AIAssistant, { config });
};
