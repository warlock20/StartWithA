/**
 * Phone card mode for Tabulator tables (#372).
 *
 * On phones a table created with `mobileCards: true` renders each row as a
 * card instead of a squeezed table row. Columns opt in through `cssClass`:
 *
 *   dt-card-title    identifying column, shown on the card's left
 *   dt-card-key      one or two key figures, stacked on the card's right
 *   dt-card-actions  row buttons, shown only while the card is open
 *
 * Every other column folds into the card's expanded section as a
 * label/value pair. The layout itself is CSS (_data-table-cards.css, phone
 * breakpoint only); this module labels the cells, toggles cards open on tap
 * and adds a sort dropdown in place of the hidden column headers.
 * Desktop rendering is unchanged.
 */

export const CARD_MEDIA_QUERY = '(max-width: 767.98px)';

export function isPhoneViewport() {
  return typeof window.matchMedia === 'function' && window.matchMedia(CARD_MEDIA_QUERY).matches;
}

/**
 * Adjust a Tabulator config before construction: label every cell with its
 * column title (used by the expanded card), and render rows without the
 * virtual DOM on phones so cards can change height when opened.
 */
export function prepareCardsConfig(config) {
  const userRowFormatter = config.rowFormatter;
  config.rowFormatter = function (row) {
    if (userRowFormatter) userRowFormatter(row);
    row.getCells().forEach((cell) => {
      const title = cell.getColumn().getDefinition().title;
      if (title) cell.getElement().dataset.label = title;
    });
  };
  if (isPhoneViewport()) config.renderVertical = 'basic';
  return config;
}

/**
 * Sort choices for the phone sort dropdown: two per sortable column, the
 * more useful direction first (largest / newest for numbers and dates,
 * A to Z for text).
 */
export function sortChoices(columnDefinitions) {
  const choices = [];
  columnDefinitions.forEach((def, index) => {
    if (!def.title || !def.field || def.headerSort === false) return;
    if (def.sorter === 'number') {
      choices.push({ index, dir: 'desc', label: `${def.title}: high to low` });
      choices.push({ index, dir: 'asc', label: `${def.title}: low to high` });
    } else if (def.sorter === 'date' || def.sorter === 'datetime') {
      choices.push({ index, dir: 'desc', label: `${def.title}: newest first` });
      choices.push({ index, dir: 'asc', label: `${def.title}: oldest first` });
    } else {
      choices.push({ index, dir: 'asc', label: `${def.title}: A to Z` });
      choices.push({ index, dir: 'desc', label: `${def.title}: Z to A` });
    }
  });
  return choices;
}

/** Open or close the card under a tap. Taps on links and controls pass through. */
export function handleCardTap(event, tableElement) {
  if (!isPhoneViewport()) return;
  if (event.target.closest('a, button, input, select, textarea, label')) return;
  const rowElement = event.target.closest('.tabulator-row');
  if (!rowElement || !tableElement.contains(rowElement)) return;
  const open = rowElement.classList.toggle('dt-card-open');
  rowElement.setAttribute('aria-expanded', String(open));
}

/** Wire card mode onto a constructed Tabulator instance. */
export function enableTableCards(table, tableElement) {
  tableElement.classList.add('dt-cards');

  const onTap = (event) => handleCardTap(event, tableElement);
  tableElement.addEventListener('click', onTap);
  let sortBar = null;

  table.on('tableBuilt', function () {
    const columns = table.getColumns();
    const keyCount = columns.filter((c) => (c.getDefinition().cssClass || '').includes('dt-card-key')).length;
    tableElement.classList.toggle('dt-cards--single-key', keyCount === 1);

    sortBar = buildSortBar(table, columns);
    if (sortBar) tableElement.parentNode.insertBefore(sortBar, tableElement);
  });

  const stopRedraw = isPhoneViewport() ? redrawWhenShown(table, tableElement) : null;

  table.on('tableDestroyed', () => {
    tableElement.removeEventListener('click', onTap);
    if (sortBar) sortBar.remove();
    if (stopRedraw) stopRedraw();
  });
}

/**
 * Tabulator only notices a hidden table becoming visible in its virtual
 * renderer. Phones use the basic one (see prepareCardsConfig), so a table
 * built inside a closed tab would stay empty when the tab opens. Redraw it
 * whenever it goes from zero width to visible. Returns a cleanup function.
 */
export function redrawWhenShown(table, tableElement) {
  if (typeof ResizeObserver === 'undefined') return null;
  let built = false;
  let width = tableElement.clientWidth;
  table.on('tableBuilt', () => { built = true; });

  const observer = new ResizeObserver(([entry]) => {
    const shown = width === 0 && entry.contentRect.width > 0;
    width = entry.contentRect.width;
    if (shown && built) table.redraw(true);
  });
  observer.observe(tableElement);
  return () => observer.disconnect();
}

function buildSortBar(table, columns) {
  const choices = sortChoices(columns.map((c) => c.getDefinition()));
  if (!choices.length) return null;

  const select = document.createElement('select');
  select.className = 'form-select form-select-sm';
  select.setAttribute('aria-label', 'Sort by');
  select.add(new Option('Sort by…', ''));
  choices.forEach((choice, i) => select.add(new Option(choice.label, String(i))));

  select.addEventListener('change', () => {
    const choice = choices[Number(select.value)];
    if (choice) table.setSort(columns[choice.index], choice.dir);
  });

  // Keep the dropdown on the active sort, however it was set.
  const syncSelect = () => {
    const active = table.getSorters()[0];
    const i = active
      ? choices.findIndex((c) => columns[c.index].getField() === active.field && c.dir === active.dir)
      : -1;
    select.value = i >= 0 ? String(i) : '';
  };
  table.on('dataSorted', syncSelect);
  syncSelect();

  const bar = document.createElement('div');
  bar.className = 'dt-card-sort';
  bar.appendChild(select);
  return bar;
}
