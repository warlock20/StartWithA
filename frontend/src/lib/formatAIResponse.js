/**
 * Format AI response text — simple markdown-like to HTML conversion.
 * Handles bold, paragraphs, bullet/numbered lists. Appends AI disclaimer.
 *
 * Port of AIResearchAssistant.formatResponseText (static method).
 *
 * @param {string} text  Raw AI response text
 * @returns {string}     HTML string
 */
export function formatAIResponse(text) {
  let formatted = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Bold
  formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Paragraphs and lists
  const paragraphs = formatted.split('\n\n');
  formatted = paragraphs
    .map((p) => {
      if (p.includes('\n- ') || p.includes('\n* ') || p.match(/^\d+\./m)) {
        let listContent = p.replace(/^- /gm, '<li>').replace(/^\* /gm, '<li>');
        listContent = listContent.replace(/^\d+\. /gm, '<li>');
        const lines = listContent
          .split('\n')
          .map((line) => (line.startsWith('<li>') ? line + '</li>' : line))
          .join('');
        return p.match(/^\d+\./m)
          ? '<ol>' + lines + '</ol>'
          : '<ul>' + lines + '</ul>';
      }
      return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    })
    .join('');

  // AI disclaimer (if globally defined by the platform)
  if (typeof window !== 'undefined' && typeof window.aiDisclaimer === 'function') {
    formatted += window.aiDisclaimer();
  }

  return formatted;
}
