import { formatAIResponse } from './lib/formatAIResponse';

/**
 * Exposes the shared AI response formatter to non-React pages.
 *
 * `free_research_step.html` and `company_detail.html` still use the class-based
 * `app/static/js/ai-research-assistant.js`, which carried its own cut-down copy
 * of this conversion. Those copies did not understand headings, links or tables,
 * so Fact-Check output — which contains all three — reached the user as literal
 * markdown. Both now delegate here so there is one implementation to maintain.
 */
window.formatAIResponse = formatAIResponse;
