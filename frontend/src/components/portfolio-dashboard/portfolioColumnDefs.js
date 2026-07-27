/**
 * Portfolio Dashboard — Tabulator column definitions.
 *
 * Three factory functions that return column definition arrays
 * for use with the DataTable React wrapper.
 */
import { ColumnFormatters } from '../../lib/columnFormatters';
import { fmtCur, fmtPct, fmtSign, plColor, plBg, sectorColor } from './portfolioUtils';

const MONO = "'JetBrains Mono', ui-monospace, monospace";

// ── Shared: Company cell (ticker bold + name gray) ──────────────────────
function companyFormatter(cell) {
  const row = cell.getRow().getData();
  const url = row.position_url || '#';
  return `<a href="${url}" style="text-decoration:none;color:inherit;">
    <div style="font-weight:600;color:var(--gray-900,#111827);font-size:15px;">${row.ticker}</div>
    <div style="font-size:13px;color:var(--gray-400,#9ca3af);margin-top:1px;">${row.name}</div>
  </a>`;
}

// ── Shared: Actions cell (Details + Txn links) ──────────────────────────
function actionsFormatter(cell) {
  const row = cell.getRow().getData();
  if (row._isCash) return '';
  return `<div style="display:flex;gap:4px;justify-content:flex-end;">
    <a href="${row.position_url}" class="rcl-action rcl-action--primary">
      <i class="bi bi-eye"></i> Details
    </a>
    <a href="${row.add_tx_url}" class="rcl-action">
      <i class="bi bi-plus"></i> Txn
    </a>
  </div>`;
}

// ═════════════════════════════════════════════════════════════════════════
// OVERVIEW TABLE
// ═════════════════════════════════════════════════════════════════════════
export function overviewColumns(currencySymbol) {
  return [
    {
      title: 'Company',
      field: 'ticker',
      sorter: 'string',
      minWidth: 160,
      widthGrow: 2,
      formatter: companyFormatter,
    },
    {
      title: 'Shares',
      field: 'shares',
      sorter: 'number',
      hozAlign: 'right',
      formatter: ColumnFormatters.number(0),
    },
    {
      title: 'Avg Cost',
      field: 'avg_cost',
      sorter: 'number',
      hozAlign: 'right',
      formatter: ColumnFormatters.currency(currencySymbol, 2),
    },
    {
      title: 'Price',
      field: 'current_price',
      sorter: 'number',
      hozAlign: 'right',
      formatter: ColumnFormatters.currency(currencySymbol, 2),
    },
    {
      title: 'Value',
      field: 'current_value',
      sorter: 'number',
      hozAlign: 'right',
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
      formatter: ColumnFormatters.gainLoss(currencySymbol, 0),
    },
    {
      title: 'Dividends',
      field: 'total_dividends',
      sorter: 'number',
      hozAlign: 'right',
      formatter: function (cell) {
        const v = cell.getValue();
        if (!v) return '<span class="table-cell-muted">--</span>';
        return `<span style="font-family:${MONO};color:var(--success-600,#059669);">${currencySymbol}${Math.round(v).toLocaleString()}</span>`;
      },
    },
    {
      title: 'Total Return',
      field: 'gain_loss_pct',
      sorter: 'number',
      hozAlign: 'right',
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
    {
      title: '',
      field: '_actions',
      headerSort: false,
      hozAlign: 'right',
      minWidth: 140,
      formatter: actionsFormatter,
    },
  ];
}

// ═════════════════════════════════════════════════════════════════════════
// WEIGHTS TABLE
// ═════════════════════════════════════════════════════════════════════════
export function weightsColumns(currencySymbol, sectorColorMap) {
  return [
    {
      title: 'Company',
      field: 'ticker',
      sorter: 'string',
      minWidth: 160,
      widthGrow: 2,
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
      formatter: function (cell) {
        const row = cell.getRow().getData();
        if (row._isCash) return '<span style="font-size:13px;color:var(--gray-400,#9ca3af);">&mdash;</span>';
        const sc = sectorColor(row.sector, sectorColorMap);
        return `<span style="display:inline-flex;align-items:center;gap:5px;padding:2px 8px;
          border-radius:4px;background:${sc}14;color:${sc};font-size:13px;font-weight:600;">
          <span style="width:6px;height:6px;border-radius:2px;background:${sc};"></span>
          ${row.sector || ''}</span>`;
      },
    },
    {
      title: 'Value',
      field: 'current_value',
      sorter: 'number',
      hozAlign: 'right',
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
      field: 'weightPortfolio',
      sorter: 'number',
      hozAlign: 'right',
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
      formatter: function (cell) {
        const row = cell.getRow().getData();
        if (row._isCash) return '<span style="color:var(--gray-400,#9ca3af);">&mdash;</span>';
        const v = cell.getValue();
        if (v == null) return '<span class="table-cell-muted">--</span>';
        return `<span style="color:var(--gray-500,#6b7280);font-family:${MONO};">${v.toFixed(1)}%</span>`;
      },
    },
    {
      title: '',
      field: '_actions',
      headerSort: false,
      hozAlign: 'right',
      minWidth: 140,
      formatter: actionsFormatter,
    },
  ];
}

// ═════════════════════════════════════════════════════════════════════════
// PERFORMANCE TABLE
// ═════════════════════════════════════════════════════════════════════════
export function performanceColumns(currencySymbol) {
  return [
    {
      title: 'Company',
      field: 'ticker',
      sorter: 'string',
      minWidth: 160,
      widthGrow: 2,
      formatter: companyFormatter,
    },
    {
      title: 'Total Return',
      field: 'gain_loss_pct',
      sorter: 'number',
      hozAlign: 'right',
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
      field: 'gain_loss',
      sorter: 'number',
      hozAlign: 'right',
      formatter: ColumnFormatters.gainLoss(currencySymbol, 0),
    },
    {
      title: 'Dividends',
      field: 'total_dividends',
      sorter: 'number',
      hozAlign: 'right',
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
    {
      title: '',
      field: '_actions',
      headerSort: false,
      hozAlign: 'right',
      minWidth: 140,
      formatter: actionsFormatter,
    },
  ];
}
