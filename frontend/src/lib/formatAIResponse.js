/**
 * Format AI response text — markdown-like to HTML conversion.
 *
 * The assistant emits richer markdown than this converter originally handled:
 * fact-check responses in particular arrive with `###` headings, `[text](url)`
 * citations and pipe tables (grounded web-search runs produce all three), while
 * `*italic*` shows up across every mode. Anything unsupported reached the user
 * as literal punctuation, so the set below tracks what the models actually
 * produce rather than a minimal subset.
 *
 * The output is injected with dangerouslySetInnerHTML, so HTML is escaped up
 * front and only this function's own tags are introduced afterwards.
 *
 * @param {string} text  Raw AI response text
 * @returns {string}     HTML string
 */

const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// Anchors are injected as raw HTML, so only http(s) is allowed through —
// `javascript:` and `data:` URLs would otherwise execute on click. Quotes and
// angle brackets are excluded so a URL cannot break out of the attribute.
const SAFE_URL = /^https?:\/\/[^\s"'<>`]+$/;

const LIST_ITEM = /^\s*[-*•]\s+(.*)$/;
const ORDERED_ITEM = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const HRULE = /^\s*([-*_])\s*(?:\1\s*){2,}$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_DIVIDER = /^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$/;

/** Inline formatting, applied to already-escaped text. */
function inline(s) {
  let out = s;

  // Bold before italic, so ** is never consumed as two single asterisks.
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*\w])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');

  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
    // Escaping ran first, so a URL's `&` is already `&amp;` — decode before
    // validating, but emit the escaped form inside the attribute.
    if (!SAFE_URL.test(url.replace(/&amp;/g, '&'))) return match;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });

  return out;
}

const splitRow = (row) =>
  row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

function renderTable(rows) {
  const [headerRow, , ...bodyRows] = rows;
  const head = splitRow(headerRow)
    .map((c) => `<th>${inline(c)}</th>`)
    .join('');
  const body = bodyRows
    .map((r) => `<tr>${splitRow(r).map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`)
    .join('');
  return (
    '<div class="table-responsive"><table class="table table-sm ai-response-table">'
    + `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
  );
}

export function formatAIResponse(text) {
  const lines = escapeHtml(text).split('\n');
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      // Cap at h6 and start at h4: these sit inside a panel, not a page.
      const level = Math.min(6, heading[1].length + 3);
      blocks.push(`<h${level} class="ai-response-heading">${inline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (HRULE.test(line)) {
      blocks.push('<hr class="ai-response-rule">');
      i += 1;
      continue;
    }

    // A table needs a header row followed by a divider row.
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_DIVIDER.test(lines[i + 1])) {
      const rows = [];
      while (i < lines.length && TABLE_ROW.test(lines[i])) {
        rows.push(lines[i]);
        i += 1;
      }
      blocks.push(renderTable(rows));
      continue;
    }

    // Consecutive list items only. Prose that happens to sit in the same
    // paragraph becomes its own block instead of a bare text child of <ul>,
    // which was invalid HTML and ran the lines together on screen.
    const isOrdered = ORDERED_ITEM.test(line);
    if (isOrdered || LIST_ITEM.test(line)) {
      const pattern = isOrdered ? ORDERED_ITEM : LIST_ITEM;
      const items = [];
      while (i < lines.length && pattern.test(lines[i])) {
        items.push(`<li>${inline(lines[i].match(pattern)[1])}</li>`);
        i += 1;
      }
      const tag = isOrdered ? 'ol' : 'ul';
      blocks.push(`<${tag}>${items.join('')}</${tag}>`);
      continue;
    }

    // Plain prose: gather until a blank line or the start of another block.
    const paragraph = [];
    while (i < lines.length && lines[i].trim()) {
      const next = lines[i];
      if (
        HEADING.test(next)
        || HRULE.test(next)
        || LIST_ITEM.test(next)
        || ORDERED_ITEM.test(next)
        || TABLE_ROW.test(next)
      ) {
        break;
      }
      paragraph.push(inline(next));
      i += 1;
    }
    if (paragraph.length) blocks.push(`<p>${paragraph.join('<br>')}</p>`);
  }

  let formatted = blocks.join('');

  // AI disclaimer (if globally defined by the platform)
  if (typeof window !== 'undefined' && typeof window.aiDisclaimer === 'function') {
    formatted += window.aiDisclaimer();
  }

  return formatted;
}
