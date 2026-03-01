/**
 * AI Disclaimer Utility
 * Returns a standard disclaimer for all AI-generated content.
 * Satisfies BaFin positioning: platform is a research tool, not Anlageberatung.
 *
 * Usage in JS:
 *   import/use globally: window.aiDisclaimer()
 *   Append to any AI response: html += aiDisclaimer();
 *
 * For Jinja templates: {% include 'main/_ai_disclaimer.html' %}
 */
function aiDisclaimer(compact) {
    if (compact) {
        return '<div class="ai-disclaimer text-muted small mt-2 fst-italic"><i class="bi bi-info-circle me-1"></i>AI-generated — not investment advice.</div>';
    }
    return '<p class="ai-disclaimer text-muted small mt-3 mb-0 fst-italic"><i class="bi bi-info-circle me-1"></i>AI-generated response — not investment advice. Verify independently before making decisions.</p>';
}

window.aiDisclaimer = aiDisclaimer;
