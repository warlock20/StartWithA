/**
 * Folded columns for Tabulator tables on desktop (#377).
 *
 * When a table's columns don't fit its panel, Tabulator's "collapse"
 * responsive layout hides the lowest-priority ones and shows them in a row
 * that opens from a chevron. Priority comes from each column's `responsive`
 * option: higher numbers fold first, 0 never folds. Columns fold when the
 * sum of their minWidths exceeds the panel, so minWidth must cover the
 * content plus the 40px of cell padding.
 *
 * Phones keep the #372 card layout instead, which already shows every
 * column when a card is opened, so folding stays off there. Like the card
 * config, this is decided once when the table is built.
 */
import { isPhoneViewport } from './tableCards';

const TOGGLE_COLUMN = {
  title: '',
  field: '_fold',
  formatter: 'responsiveCollapse',
  cssClass: 'dt-fold-toggle',
  width: 44,
  minWidth: 44,
  hozAlign: 'center',
  headerSort: false,
  resizable: false,
  responsive: 0,
};

const TOGGLE_SELECTOR = '.tabulator-responsive-collapse-toggle';

/** Adjust a Tabulator config before construction to fold columns that don't fit. */
export function prepareFoldConfig(config) {
  if (isPhoneViewport()) return config;
  config.responsiveLayout = 'collapse';
  config.responsiveLayoutCollapseStartOpen = false;
  config.responsiveLayoutCollapseFormatter = formatFoldedData;
  config.columns = [{ ...TOGGLE_COLUMN }, ...config.columns];

  const userRowFormatter = config.rowFormatter;
  config.rowFormatter = function (row) {
    if (userRowFormatter) userRowFormatter(row);
    labelFoldToggle(row.getElement());
  };
  return config;
}

/**
 * Tabulator draws the toggle as a bare div. Give it button semantics so it
 * can be reached and announced; handleFoldKey makes Enter and Space work.
 */
export function labelFoldToggle(rowElement) {
  const toggle = rowElement.querySelector(TOGGLE_SELECTOR);
  if (!toggle) return;
  toggle.setAttribute('role', 'button');
  toggle.setAttribute('tabindex', '0');
  toggle.setAttribute('aria-label', 'Show more columns');
  toggle.setAttribute('aria-expanded', String(toggle.classList.contains('open')));
}

/** Enter or Space on a focused toggle opens or closes its row. */
export function handleFoldKey(event) {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const toggle = event.target.closest(TOGGLE_SELECTOR);
  if (!toggle) return;
  event.preventDefault();
  toggle.click();
}

/** Wire keyboard support and aria-expanded onto a constructed table. */
export function enableTableFold(table, tableElement) {
  // Tabulator fixes the header height before folding narrows the columns,
  // which clips wrapped titles; _data-table-fold.css sizes them to content.
  tableElement.classList.add('dt-fold');

  // Tabulator's own click handler stops propagation, so listen while
  // capturing and read the toggled state once it has run.
  const onClick = (event) => {
    const toggle = event.target.closest(TOGGLE_SELECTOR);
    if (!toggle) return;
    queueMicrotask(() => toggle.setAttribute('aria-expanded', String(toggle.classList.contains('open'))));
  };
  tableElement.addEventListener('click', onClick, true);
  tableElement.addEventListener('keydown', handleFoldKey);
  table.on('tableDestroyed', () => {
    tableElement.removeEventListener('click', onClick, true);
    tableElement.removeEventListener('keydown', handleFoldKey);
  });
}

/**
 * Render folded columns as label/value pairs. Values arrive already run
 * through the column formatters, as an HTML string or a DOM node.
 */
export function formatFoldedData(items) {
  if (!items.length) return '';
  const list = document.createElement('div');
  list.className = 'dt-fold-pairs';
  items.forEach((item) => {
    const pair = document.createElement('div');
    pair.className = 'dt-fold-pair';

    const label = document.createElement('span');
    label.className = 'dt-fold-label';
    label.textContent = item.title;

    const value = document.createElement('span');
    value.className = 'dt-fold-value';
    if (item.value instanceof Node) value.appendChild(item.value);
    else value.innerHTML = item.value ?? '';

    pair.append(label, value);
    list.appendChild(pair);
  });
  return list;
}
