/**
 * Reusable Data Table utilities — ES module version.
 *
 * Wraps Tabulator.js (loaded via CDN as window.Tabulator) with
 * platform-standard defaults, scroll indicators, and export support.
 *
 * Usage in React islands:
 *   import { createDataTable, quickFilter, refreshTableData } from '../lib/dataTable';
 *   import { ColumnFormatters } from '../lib/columnFormatters';
 */
export { ColumnFormatters } from './columnFormatters';

const DEFAULT_TABLE_CONFIG = {
  layout: 'fitData',
  pagination: true,
  paginationSize: 25,
  paginationSizeSelector: [10, 25, 50, 100],
  movableColumns: false,
  resizableColumns: true,
  headerSort: true,
  placeholder: 'No data available',
  tooltips: true,
  history: false,
};

/**
 * Create a data table with platform styling.
 *
 * @param {string} selector  CSS selector for the table element
 * @param {object} options   Table configuration (columns, data/ajaxURL, etc.)
 * @returns {Tabulator|null} Tabulator instance
 */
export function createDataTable(selector, options = {}) {
  if (!selector) {
    console.error('createDataTable: selector is required');
    return null;
  }
  if (!options.columns || !Array.isArray(options.columns)) {
    console.error('createDataTable: columns array is required');
    return null;
  }

  const Tabulator = window.Tabulator;
  if (!Tabulator) {
    console.error('createDataTable: Tabulator is not loaded');
    return null;
  }

  const config = { ...DEFAULT_TABLE_CONFIG, columns: options.columns };

  if (options.data) {
    config.data = options.data;
  } else if (options.ajaxURL) {
    config.ajaxURL = options.ajaxURL;
    config.ajaxResponse =
      options.ajaxResponse ||
      function (_url, _params, response) {
        return response.data || response;
      };
  }

  if (options.headerFilters) {
    config.columns = config.columns.map((col) => ({
      ...col,
      headerFilter: col.headerFilter !== false ? col.headerFilter || 'input' : false,
    }));
  }

  if (options.rowFormatter) config.rowFormatter = options.rowFormatter;
  if (options.rowClick) config.rowClick = options.rowClick;
  if (options.customConfig) Object.assign(config, options.customConfig);

  const table = new Tabulator(selector, config);

  // Scroll indicator for horizontally scrollable tables
  const tableElement = document.querySelector(selector);
  if (tableElement) {
    const wrapper = tableElement.closest('.data-table-wrapper');
    if (wrapper) {
      const SCROLL_END_THRESHOLD = 5;
      table.on('tableBuilt', function () {
        const holder = tableElement.querySelector('.tabulator-tableholder');
        if (!holder) return;

        const update = () => {
          const atEnd = holder.scrollLeft + holder.clientWidth >= holder.scrollWidth - SCROLL_END_THRESHOLD;
          wrapper.classList.toggle('scrolled-end', atEnd);
        };

        let ticking = false;
        const onScroll = () => {
          if (!ticking) {
            window.requestAnimationFrame(() => { update(); ticking = false; });
            ticking = true;
          }
        };

        holder.addEventListener('scroll', onScroll);
        update();
        table.on('tableDestroyed', () => holder.removeEventListener('scroll', onScroll));
      });
    }
  }

  // Export buttons
  if (options.exportButtons) {
    const exportConfig = options.exportConfig || {};
    const el = document.querySelector(selector);
    const w = el?.closest('.data-table-wrapper');
    const controls = w?.querySelector('.data-table-controls');
    if (controls) addExportButtons(controls, table, exportConfig);
  }

  return table;
}

function addExportButtons(container, table, config = {}) {
  const group = document.createElement('div');
  group.className = 'd-flex gap-2';

  if (config.csv !== false) {
    group.appendChild(makeBtn('CSV', 'bi-filetype-csv', () => table.download('csv', `${config.filename || 'data'}.csv`)));
  }
  if (config.xlsx) {
    group.appendChild(makeBtn('Excel', 'bi-file-earmark-excel', () => table.download('xlsx', `${config.filename || 'data'}.xlsx`, { sheetName: config.sheetName || 'Data' })));
  }
  if (config.json) {
    group.appendChild(makeBtn('JSON', 'bi-filetype-json', () => table.download('json', `${config.filename || 'data'}.json`)));
  }

  container.appendChild(group);
}

function makeBtn(label, icon, onClick) {
  const btn = document.createElement('button');
  btn.className = 'data-table-export-btn';
  btn.innerHTML = `<i class="bi ${icon}"></i> ${label}`;
  btn.addEventListener('click', onClick);
  return btn;
}

/** Quick filter helper. Pass 'all' or empty to clear. */
export function quickFilter(table, field, value) {
  if (!value || value === 'all') {
    table.clearFilter();
  } else {
    table.setFilter(field, '=', value);
  }
}

/** Refresh table data from AJAX source. */
export function refreshTableData(table) {
  if (table && table.replaceData) table.replaceData();
}
