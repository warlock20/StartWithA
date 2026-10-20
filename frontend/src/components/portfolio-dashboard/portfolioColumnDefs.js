/**
 * Portfolio Dashboard — Tabulator column definitions.
 *
 * Three factory functions that return column definition arrays
 * for use with the DataTable React wrapper.
 *
 * The dt-card-* classes pick what a phone card shows (see lib/tableCards).
 * On desktop, columns that don't fit fold into an expandable row (see
 * lib/tableFold): minWidth is the content width plus 40px of cell padding,
 * and `responsive` sets the fold order (higher folds first, 0 never).
 */
import { ColumnFormatters } from '../../lib/columnFormatters';
import { fmtCur, fmtPct, fmtSign, plColor, plBg, sectorColor, escapeHtml } from './portfolioUtils';

const MONO = "'JetBrains Mono', ui-monospace, monospace";

// ── Shared: Company cell (ticker bold + name gray) ──────────────────────
function companyFormatter(cell) {
  const row = cell.getRow().getData();
  const url = row.position_url || '#';
  return `<a href="${url}" style="text-decoration:none;color:inherit;">
    <div style="font-weight:600;color:var(--gray-900,#111827);font-size:15px;">${row.ticker}</div>
    <div title="${escapeHtml(row.name)}" style="font-size:13px;color:var(--gray-400,#9ca3af);margin-top:1px;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${row.name}</div>
  </a>`;
}

// ── Shared: Actions cell (Details + Txn links) ──────────────────────────
// Icon-only on desktop; phone cards show the labels.
function actionsFormatter(cell) {
  const row = cell.getRow().getData();
  if (row._isCash) return '';
  return `<div style="display:flex;gap:4px;justify-content:flex-end;">
    <a href="${row.position_url}" class="rcl-action rcl-action--primary" title="Details" aria-label="Details">
      <i class="bi bi-eye"></i><span class="dt-action-label">Details</span>
    </a>
    <a href="${row.add_tx_url}" class="rcl-action" title="Add transaction" aria-label="Add transaction">
      <i class="bi bi-plus"></i><span class="dt-action-label">Txn</span>
    </a>
  </div>`;
}

const ACTIONS_COLUMN = {
  title: '',
  field: '_actions',
  cssClass: 'dt-card-actions',
  headerSort: false,
  hozAlign: 'right',
  minWidth: 110,
  responsive: 0,
  formatter: actionsFormatter,
};

const COMPANY_COLUMN = {
  title: 'Company',
  cssClass: 'dt-card-title',
  field: 'ticker',
  sorter: 'string',
  minWidth: 160,
  widthGrow: 2,
  responsive: 0,
};

// ═════════════════════════════════════════════════════════════════════════
// OVERVIEW TABLE
// ═════════════════════════════════════════════════════════════════════════
export function overviewColumns(currencySymbol) {
  return [
    { ...COMPANY_COLUMN, formatter: companyFormatter },
    {
      title: 'Shares',
      field: 'shares',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 120,
      responsive: 3,
      formatter: ColumnFormatters.number(0),
    },
    {
      title: 'Avg Cost',
      field: 'avg_cost',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 4,
      headerWordWrap: true,
      formatter: ColumnFormatters.currency(currencySymbol, 2),
    },
    {
      title: 'Price',
      field: 'current_price',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 2,
      formatter: ColumnFormatters.currency(currencySymbol, 2),
    },
    {
      title: 'Value',
      cssClass: 'dt-card-key',
      field: 'current_value',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 0,
      formatter: function (cell) {
        const v = cell.getValue();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<strong>${currencySymbol}${Math.round(v).toLocaleString()}</strong>`;
      },
    },
    {
      title: 'Total P/L',
      field: 'gain_loss',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 1,
      headerWordWrap: true,
      formatter: ColumnFormatters.gainLoss(currencySymbol, 0),
    },
    {
      title: 'Dividends',
      field: 'total_dividends',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 140,
      responsive: 5,
      formatter: function (cell) {
        const v = cell.getValue();
        if (!v) return '<span class="table-cell-muted">--</span>';
        return `<span style="font-family:${MONO};color:var(--success-600,#059669);">${currencySymbol}${Math.round(v).toLocaleString()}</span>`;
      },
    },
    {
      title: 'Total Return',
      cssClass: 'dt-card-key',
      field: 'gain_loss_pct',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 120,
      responsive: 0,
      headerWordWrap: true,
      formatter: function (cell) {
        const v = cell.getValue();
        const row = cell.getRow().getData();
        const gl = row.gain_loss || 0;
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;
          background:${plBg(gl)};color:${plColor(gl)};font-size:14px;font-weight:600;
          font-family:${MONO};">${fmtPct(v)}</span>`;
      },
    },
    ACTIONS_COLUMN,
  ];
}

// ═════════════════════════════════════════════════════════════════════════
// WEIGHTS TABLE
// ═════════════════════════════════════════════════════════════════════════
export function weightsColumns(currencySymbol, sectorColorMap) {
  return [
    {
      ...COMPANY_COLUMN,
      formatter: function (cell) {
        const row = cell.getRow().getData();
        if (row._isCash) {
          return '<div style="font-weight:600;color:var(--gray-500,#6b7280);font-size:15px;font-style:italic;">Cash</div>';
        }
        return companyFormatter(cell);
      },
    },
    {
      title: 'Sector',
      field: 'sector',
      sorter: 'string',
      minWidth: 160,
      responsive: 1,
      formatter: function (cell) {
        const row = cell.getRow().getData();
        if (row._isCash) return '<span style="font-size:13px;color:var(--gray-400,#9ca3af);">&mdash;</span>';
        const sc = sectorColor(row.sector, sectorColorMap);
        const name = escapeHtml(row.sector || '');
        // Long sector names ellipsize inside the badge; the tooltip has the full name.
        return `<span title="${name}" style="display:inline-flex;align-items:center;gap:5px;padding:2px 8px;
          max-width:100%;border-radius:4px;background:${sc}14;color:${sc};font-size:13px;font-weight:600;">
          <span style="flex:none;width:6px;height:6px;border-radius:2px;background:${sc};"></span>
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</span></span>`;
      },
    },
    {
      title: 'Value',
      cssClass: 'dt-card-key',
      field: 'current_value',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 0,
      formatter: function (cell) {
        const v = cell.getValue();
        const row = cell.getRow().getData();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        const style = row._isCash ? 'color:var(--gray-500,#6b7280);' : '';
        return `<strong style="${style}">${currencySymbol}${Math.round(v).toLocaleString()}</strong>`;
      },
    },
    {
      title: 'Weight',
      cssClass: 'dt-card-key',
      field: 'weightPortfolio',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 120,
      responsive: 0,
      formatter: function (cell) {
        const v = cell.getValue();
        const row = cell.getRow().getData();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        const style = row._isCash ? 'color:var(--gray-500,#6b7280);' : '';
        return `<strong style="font-family:${MONO};${style}">${v.toFixed(1)}%</strong>`;
      },
    },
    {
      title: 'Allocation',
      field: 'weightPortfolio',
      headerSort: false,
      minWidth: 140,
      responsive: 2,
      formatter: function (cell) {
        const v = cell.getValue() || 0;
        const row = cell.getRow().getData();
        const color = row._isCash ? '#94a3b8' : sectorColor(row.sector, sectorColorMap);
        return `<div style="width:100%;max-width:120px;height:6px;background:var(--gray-100,#f3f4f6);
          border-radius:3px;overflow:hidden;">
          <div style="height:100%;width:${Math.min(v, 100)}%;background:${color};
            border-radius:3px;transition:width .3s ease;"></div>
        </div>`;
      },
    },
    {
      title: 'Equity %',
      field: 'weightEquity',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 3,
      headerWordWrap: true,
      formatter: function (cell) {
        const row = cell.getRow().getData();
        if (row._isCash) return '<span style="color:var(--gray-400,#9ca3af);">&mdash;</span>';
        const v = cell.getValue();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<span style="color:var(--gray-500,#6b7280);font-family:${MONO};">${v.toFixed(1)}%</span>`;
      },
    },
    ACTIONS_COLUMN,
  ];
}

// ═════════════════════════════════════════════════════════════════════════
// PERFORMANCE TABLE
// ═════════════════════════════════════════════════════════════════════════
export function performanceColumns(currencySymbol) {
  return [
    { ...COMPANY_COLUMN, formatter: companyFormatter },
    {
      title: 'Total Return',
      cssClass: 'dt-card-key',
      field: 'gain_loss_pct',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 120,
      responsive: 0,
      headerWordWrap: true,
      formatter: function (cell) {
        const v = cell.getValue();
        const row = cell.getRow().getData();
        const gl = row.gain_loss || 0;
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<span style="display:inline-block;padding:3px 10px;border-radius:6px;
          background:${plBg(gl)};color:${plColor(gl)};font-size:15px;font-weight:700;
          font-family:${MONO};">${fmtPct(v)}</span>`;
      },
    },
    {
      title: 'Total P/L',
      cssClass: 'dt-card-key',
      field: 'gain_loss',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 112,
      responsive: 0,
      headerWordWrap: true,
      formatter: ColumnFormatters.gainLoss(currencySymbol, 0),
    },
    {
      title: 'Dividends',
      field: 'total_dividends',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 140,
      responsive: 1,
      formatter: function (cell) {
        const v = cell.getValue();
        if (!v) return '<span class="table-cell-muted">--</span>';
        return `<span style="font-family:${MONO};color:var(--success-600,#059669);">${currencySymbol}${Math.round(v).toLocaleString()}</span>`;
      },
    },
    {
      title: 'Cost \u2192 Value',
      field: 'current_value',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 200,
      responsive: 2,
      headerWordWrap: true,
      formatter: function (cell) {
        const row = cell.getRow().getData();
        return `<span style="color:var(--gray-400,#9ca3af);font-family:${MONO};">${fmtCur(row.cost_basis, currencySymbol)}</span>
          <span style="color:var(--gray-300,#d1d5db);margin:0 4px;">\u2192</span>
          <span style="font-weight:600;color:var(--text-primary,#374151);font-family:${MONO};">${fmtCur(row.current_value, currencySymbol)}</span>`;
      },
    },
    {
      title: 'Days Held',
      field: 'days_held',
      sorter: 'number',
      hozAlign: 'center',
      minWidth: 112,
      responsive: 3,
      headerWordWrap: true,
      formatter: function (cell) {
        const v = cell.getValue();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;
          background:var(--gray-100,#f3f4f6);font-size:14px;font-weight:500;
          font-family:${MONO};color:var(--gray-500,#6b7280);">${v}d</span>`;
      },
    },
    {
      title: 'Daily P/L',
      field: 'gain_loss',
      sorter: 'number',
      hozAlign: 'right',
      minWidth: 120,
      responsive: 4,
      headerWordWrap: true,
      formatter: function (cell) {
        const row = cell.getRow().getData();
        const dailyPL = row.days_held > 0 ? (row.gain_loss || 0) / row.days_held : 0;
        const color = plColor(dailyPL);
        return `<span style="font-family:${MONO};font-size:14px;color:${color};">${fmtSign(dailyPL, currencySymbol)}/d</span>`;
      },
      sorterParams: {
        alignEmptyValues: 'bottom',
      },
    },
    ACTIONS_COLUMN,
  ];
}
