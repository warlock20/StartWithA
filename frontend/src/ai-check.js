import { mountIsland } from './lib/mountIsland';
import { AICheck } from './components/ai-check/AICheck';

/**
 * AI check — React island entry (research_step.html).
 * Exposes `window.initAICheck(elementId, config)`; the component exposes
 * `window.aiCheck.updateContext({ itemId, hasAiContext })` for AJAX item navigation.
 */
window.initAICheck = function (elementId, config) {
  return mountIsland(elementId, AICheck, { config });
};
