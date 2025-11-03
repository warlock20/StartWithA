/**
 * =============================================================================
 * REUSABLE DATA TABLE COMPONENT
 * =============================================================================
 *
 * Platform-wide table component using Tabulator.
 * Provides consistent styling, filtering, sorting, and export functionality.
 *
 * Usage:
 * ------
 * const table = createDataTable('#my-table', {
 *     data: [...],
 *     columns: [...]
 * });
 *
 * Documentation: See README section in this file
 */

/**
 * Default configuration for all data tables
 * These settings ensure consistency across the platform
 */
const DEFAULT_TABLE_CONFIG = {
    layout: "fitData",              // Columns fit data by default
    responsiveLayout: "collapse",   // Stack columns on mobile
    pagination: true,               // Enable pagination
    paginationSize: 25,             // 25 rows per page
    paginationSizeSelector: [10, 25, 50, 100],
    movableColumns: false,          // Prevent accidental column reordering
    resizableColumns: true,         // Allow column resizing
    headerSort: true,               // Enable column sorting
    placeholder: "No data available", // Empty state message
    tooltips: true,                 // Show tooltips on cells
    history: false,                 // Disable undo/redo for performance
};

/**
 * Create a data table with platform styling
 *
 * @param {string} selector - CSS selector for table element (e.g., '#holdings-table')
 * @param {object} options - Table configuration options
 * @param {array} options.columns - Column definitions (required)
 * @param {array} options.data - Table data (optional, can use AJAX instead)
 * @param {string} options.ajaxURL - URL to fetch data from (optional)
 * @param {boolean} options.headerFilters - Enable column filtering (default: false)
 * @param {boolean} options.exportButtons - Show export buttons (default: false)
 * @param {object} options.exportConfig - Export configuration (optional)
 * @param {function} options.rowFormatter - Custom row formatter (optional)
 * @param {function} options.rowClick - Row click handler (optional)
 * @param {object} options.customConfig - Override any Tabulator config (optional)
 *
 * @returns {Tabulator} - Tabulator instance
 */
function createDataTable(selector, options = {}) {
    // Validate required parameters
    if (!selector) {
        console.error('createDataTable: selector is required');
        return null;
    }

    if (!options.columns || !Array.isArray(options.columns)) {
        console.error('createDataTable: columns array is required');
        return null;
    }

    // Build Tabulator configuration
    const config = {
        ...DEFAULT_TABLE_CONFIG,
        columns: options.columns,
    };

    // Add data source (either static data or AJAX)
    if (options.data) {
        config.data = options.data;
    } else if (options.ajaxURL) {
        config.ajaxURL = options.ajaxURL;
        config.ajaxResponse = options.ajaxResponse || function(url, params, response) {
            return response.data || response;
        };
    }

    // Enable header filters if requested
    if (options.headerFilters) {
        config.columns = config.columns.map(col => ({
            ...col,
            headerFilter: col.headerFilter !== false ? (col.headerFilter || "input") : false
        }));
    }

    // Add row formatter if provided
    if (options.rowFormatter) {
        config.rowFormatter = options.rowFormatter;
    }

    // Add row click handler if provided
    if (options.rowClick) {
        config.rowClick = options.rowClick;
    }

    // Merge custom configuration (allows override)
    if (options.customConfig) {
        Object.assign(config, options.customConfig);
    }

    // Initialize Tabulator
    const table = new Tabulator(selector, config);

    // Add export functionality if requested
    if (options.exportButtons) {
        const exportConfig = options.exportConfig || {};

        // Find or create export button container
        const tableElement = document.querySelector(selector);
        const wrapper = tableElement.closest('.data-table-wrapper');

        if (wrapper) {
            const controls = wrapper.querySelector('.data-table-controls');
            if (controls) {
                addExportButtons(controls, table, exportConfig);
            }
        }
    }

    return table;
}

/**
 * Add export buttons to table controls
 *
 * @param {HTMLElement} container - Container element for buttons
 * @param {Tabulator} table - Tabulator instance
 * @param {object} config - Export configuration
 */
function addExportButtons(container, table, config = {}) {
    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'd-flex gap-2';

    // CSV Export
    if (config.csv !== false) {
        const csvBtn = createExportButton('CSV', 'bi-filetype-csv', () => {
            table.download("csv", `${config.filename || 'data'}.csv`);
        });
        buttonGroup.appendChild(csvBtn);
    }

    // Excel Export
    if (config.xlsx) {
        const xlsxBtn = createExportButton('Excel', 'bi-file-earmark-excel', () => {
            table.download("xlsx", `${config.filename || 'data'}.xlsx`, {
                sheetName: config.sheetName || "Data"
            });
        });
        buttonGroup.appendChild(xlsxBtn);
    }

    // JSON Export
    if (config.json) {
        const jsonBtn = createExportButton('JSON', 'bi-filetype-json', () => {
            table.download("json", `${config.filename || 'data'}.json`);
        });
        buttonGroup.appendChild(jsonBtn);
    }

    container.appendChild(buttonGroup);
}

/**
 * Create an export button
 *
 * @param {string} label - Button label
 * @param {string} icon - Bootstrap icon class
 * @param {function} onClick - Click handler
 * @returns {HTMLElement} - Button element
 */
function createExportButton(label, icon, onClick) {
    const btn = document.createElement('button');
    btn.className = 'data-table-export-btn';
    btn.innerHTML = `<i class="bi ${icon}"></i> ${label}`;
    btn.addEventListener('click', onClick);
    return btn;
}

/**
 * Common column formatters for reuse across tables
 */
const ColumnFormatters = {
    /**
     * Format currency values
     * @param {number} value - Amount to format
     * @param {string} symbol - Currency symbol (default: $)
     * @param {number} decimals - Decimal places (default: 2)
     */
    currency: (symbol = '$', decimals = 2) => {
        return function(cell) {
            const value = cell.getValue();
            if (value === null || value === undefined || value === '') {
                return '<span class="table-cell-muted">--</span>';
            }
            const formatted = parseFloat(value).toFixed(decimals);
            return `${symbol}${formatted}`;
        };
    },

    /**
     * Format percentage values
     * @param {number} decimals - Decimal places (default: 2)
     * @param {boolean} colorize - Add color based on positive/negative (default: true)
     */
    percentage: (decimals = 2, colorize = true) => {
        return function(cell) {
            const value = cell.getValue();
            if (value === null || value === undefined || value === '') {
                return '<span class="table-cell-muted">--</span>';
            }
            const formatted = parseFloat(value).toFixed(decimals);
            const sign = value >= 0 ? '+' : '';
            const colorClass = colorize ? (value >= 0 ? 'table-cell-success' : 'table-cell-danger') : '';
            return `<span class="${colorClass}">${sign}${formatted}%</span>`;
        };
    },

    /**
     * Format gain/loss values with color
     * @param {string} symbol - Currency symbol (default: $)
     * @param {number} decimals - Decimal places (default: 2)
     */
    gainLoss: (symbol = '$', decimals = 2) => {
        return function(cell) {
            const value = cell.getValue();
            if (value === null || value === undefined || value === '') {
                return '<span class="table-cell-muted">--</span>';
            }
            const formatted = parseFloat(value).toFixed(decimals);
            const sign = value >= 0 ? '+' : '';
            const colorClass = value >= 0 ? 'table-cell-success' : 'table-cell-danger';
            return `<strong class="${colorClass}">${sign}${symbol}${formatted}</strong>`;
        };
    },

    /**
     * Format date values
     * @param {string} format - Date format ('short', 'long', 'iso') (default: 'short')
     */
    date: (format = 'short') => {
        return function(cell) {
            const value = cell.getValue();
            if (!value) return '<span class="table-cell-muted">--</span>';

            const date = new Date(value);
            if (format === 'iso') {
                return date.toISOString().split('T')[0];
            } else if (format === 'long') {
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            } else {
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });
            }
        };
    },

    /**
     * Format badge (like transaction type, status)
     * @param {object} colorMap - Map of values to Bootstrap color classes
     */
    badge: (colorMap = {}) => {
        return function(cell) {
            const value = cell.getValue();
            if (!value) return '';

            const colorClass = colorMap[value] || 'bg-secondary';
            return `<span class="badge ${colorClass}">${value}</span>`;
        };
    },

    /**
     * Format number with thousand separators
     * @param {number} decimals - Decimal places (default: 0)
     */
    number: (decimals = 0) => {
        return function(cell) {
            const value = cell.getValue();
            if (value === null || value === undefined || value === '') {
                return '<span class="table-cell-muted">--</span>';
            }
            return parseFloat(value).toLocaleString('en-US', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            });
        };
    },

    /**
     * Format action buttons
     * @param {array} buttons - Array of button configurations
     * Example: [{label: 'View', icon: 'bi-eye', onClick: (row) => {}}]
     */
    actions: (buttons = []) => {
        return function(cell) {
            const row = cell.getRow();
            const btnGroup = document.createElement('div');
            btnGroup.className = 'btn-group btn-group-sm';

            buttons.forEach(btn => {
                const button = document.createElement('button');
                button.className = `btn ${btn.class || 'btn-outline-primary'}`;
                button.innerHTML = `<i class="bi ${btn.icon}"></i>`;
                button.title = btn.label || '';
                button.addEventListener('click', () => btn.onClick(row.getData()));
                btnGroup.appendChild(button);
            });

            return btnGroup;
        };
    }
};

/**
 * Quick filter helper for tables
 * Adds a custom filter function to table
 *
 * @param {Tabulator} table - Tabulator instance
 * @param {string} field - Field to filter on
 * @param {string} value - Value to filter for
 */
function quickFilter(table, field, value) {
    if (!value || value === 'all') {
        table.clearFilter();
    } else {
        table.setFilter(field, "=", value);
    }
}

/**
 * Refresh table data from AJAX source
 *
 * @param {Tabulator} table - Tabulator instance
 */
function refreshTableData(table) {
    if (table && table.replaceData) {
        table.replaceData();
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createDataTable,
        ColumnFormatters,
        quickFilter,
        refreshTableData
    };
}

/**
 * =============================================================================
 * USAGE EXAMPLES
 * =============================================================================
 *
 * Example 1: Basic Portfolio Holdings Table
 * ------------------------------------------
 * const holdings = createDataTable('#holdings-table', {
 *     data: portfolioData,
 *     columns: [
 *         { title: "Company", field: "ticker", sorter: "string" },
 *         { title: "Shares", field: "shares", sorter: "number", hozAlign: "right" },
 *         { title: "Value", field: "value", formatter: ColumnFormatters.currency(), hozAlign: "right" },
 *         { title: "Gain/Loss", field: "gainLoss", formatter: ColumnFormatters.gainLoss(), hozAlign: "right" },
 *         { title: "%", field: "gainLossPct", formatter: ColumnFormatters.percentage(), hozAlign: "right" }
 *     ],
 *     exportButtons: true,
 *     exportConfig: { filename: 'portfolio-holdings' }
 * });
 *
 * Example 2: Table with Header Filters
 * -------------------------------------
 * const transactions = createDataTable('#transactions-table', {
 *     ajaxURL: '/api/transactions',
 *     columns: [
 *         { title: "Date", field: "date", formatter: ColumnFormatters.date(), sorter: "date" },
 *         { title: "Type", field: "type", formatter: ColumnFormatters.badge({
 *             'BUY': 'bg-primary',
 *             'SELL': 'bg-danger',
 *             'DIVIDEND': 'bg-success'
 *         }) },
 *         { title: "Company", field: "ticker" },
 *         { title: "Shares", field: "quantity", hozAlign: "right" }
 *     ],
 *     headerFilters: true
 * });
 *
 * Example 3: Table with Quick Filter Dropdown
 * --------------------------------------------
 * // HTML: <select id="status-filter" class="form-select">...</select>
 *
 * const table = createDataTable('#my-table', { ... });
 *
 * document.getElementById('status-filter').addEventListener('change', (e) => {
 *     quickFilter(table, 'status', e.target.value);
 * });
 *
 * Example 4: Table with Row Click Handler
 * ----------------------------------------
 * const table = createDataTable('#clickable-table', {
 *     columns: [...],
 *     data: [...],
 *     rowClick: function(e, row) {
 *         const data = row.getData();
 *         window.location.href = `/position/${data.id}`;
 *     }
 * });
 */
