/**
 * Utility functions for the sector canvas.
 */

export function escapeHtml(str) {
  if (!str) return '';
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Convert BlockNote JSON content to preview HTML.
 */
export function blocknoteToPreviewHtml(contentJson) {
  try {
    var blocks = JSON.parse(contentJson);
    if (!Array.isArray(blocks)) return escapeHtml(contentJson);
    return blocks
      .map(function (block) {
        if (block.content && Array.isArray(block.content)) {
          var text = block.content
            .filter(function (item) { return item && item.type === 'text'; })
            .map(function (item) { return item.text || ''; })
            .join('');
          if (!text) return '';
          var tag = block.type === 'heading' ? 'h3' : 'p';
          return '<' + tag + '>' + escapeHtml(text) + '</' + tag + '>';
        }
        return '';
      })
      .filter(Boolean)
      .join('');
  } catch (e) {
    return escapeHtml(contentJson);
  }
}

/**
 * Map for note type display.
 */
export var NOTE_TYPE_META = {
  ai_insight: { icon: 'bi-sparkles', label: 'AI Insight', className: 'ai-insight' },
  web_clip: { icon: 'bi-scissors', label: 'Web Clip', className: 'web-clip' },
  snippet: { icon: 'bi-bookmark', label: 'Snippet', className: 'snippet' },
  company_insight: { icon: 'bi-building', label: 'Company Insight', className: 'company-insight' },
  note: { icon: 'bi-pencil', label: 'Note', className: '' },
};

/**
 * Wrapper for window.showToast that maps 'error' → 'danger'.
 */
export function showToast(message, type) {
  if (window.showToast) {
    window.showToast(message, type === 'error' ? 'danger' : type);
  }
}
