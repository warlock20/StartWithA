/**
 * Common column formatters for Tabulator-based data tables.
 *
 * ES module version of the formatters from data-table-component.js.
 * Each formatter is a factory function that returns a Tabulator cell formatter.
 *
 * Usage in React islands:
 *   import { ColumnFormatters } from '../lib/columnFormatters';
 *   { title: "Value", field: "value", formatter: ColumnFormatters.currency() }
 */
export const ColumnFormatters = {
  /** Format currency values. Returns "--" for null/empty. */
  currency: (symbol = '$', decimals = 2) => {
    return function (cell) {
      const value = cell.getValue();
      if (value === null || value === undefined || value === '') {
        return '<span class="table-cell-muted">--</span>';
      }
      return `${symbol}${parseFloat(value).toFixed(decimals)}`;
    };
  },

  /** Format percentage values with optional color (green/red). */
  percentage: (decimals = 2, colorize = true) => {
    return function (cell) {
      const value = cell.getValue();
      if (value === null || value === undefined || value === '') {
        return '<span class="table-cell-muted">--</span>';
      }
      const formatted = parseFloat(value).toFixed(decimals);
      const sign = value >= 0 ? '+' : '';
      const colorClass = colorize
        ? value >= 0 ? 'table-cell-success' : 'table-cell-danger'
        : '';
      return `<span class="${colorClass}">${sign}${formatted}%</span>`;
    };
  },

  /** Format gain/loss with bold colored text. */
  gainLoss: (symbol = '$', decimals = 2) => {
    return function (cell) {
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

  /** Format date values. Supports 'short', 'long', 'iso'. */
  date: (format = 'short') => {
    return function (cell) {
      const value = cell.getValue();
      if (!value) return '<span class="table-cell-muted">--</span>';

      const date = new Date(value);
      if (format === 'iso') return date.toISOString().split('T')[0];
      if (format === 'long') {
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      }
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    };
  },

  /** Format badge (status, type). colorMap maps values to Bootstrap bg classes. */
  badge: (colorMap = {}) => {
    return function (cell) {
      const value = cell.getValue();
      if (!value) return '';
      const colorClass = colorMap[value] || 'bg-secondary';
      return `<span class="badge ${colorClass}">${value}</span>`;
    };
  },

  /** Format number with thousand separators. */
  number: (decimals = 0) => {
    return function (cell) {
      const value = cell.getValue();
      if (value === null || value === undefined || value === '') {
        return '<span class="table-cell-muted">--</span>';
      }
      return parseFloat(value).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    };
  },

  /** Format action buttons. buttons: [{label, icon, onClick, class}] */
  actions: (buttons = []) => {
    return function (cell) {
      const row = cell.getRow();
      const btnGroup = document.createElement('div');
      btnGroup.className = 'btn-group btn-group-sm';

      buttons.forEach((btn) => {
        const button = document.createElement('button');
        button.className = `btn ${btn.class || 'btn-outline-primary'}`;
        button.innerHTML = `<i class="bi ${btn.icon}"></i>`;
        button.title = btn.label || '';
        button.addEventListener('click', () => btn.onClick(row.getData()));
        btnGroup.appendChild(button);
      });

      return btnGroup;
    };
  },
};
