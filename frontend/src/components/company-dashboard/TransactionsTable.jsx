import { useEffect, useRef } from 'react';
import { createDataTable } from '../../lib/dataTable';

/**
 * Column definitions for the company transactions table.
 *
 * The dt-card-* classes pick what a phone card shows (see lib/tableCards).
 * On desktop, columns that don't fit fold into an expandable row (see
 * lib/tableFold): minWidth is the content width plus the cell padding, and
 * `responsive` sets the fold order (higher folds first, 0 never).
 */
export function transactionColumns(currencySymbol) {
  var cs = currencySymbol;
  return [
    {
      title: 'Date',
      field: 'date',
      cssClass: 'dt-card-title',
      sorter: 'date',
      sorterParams: { format: 'yyyy-MM-dd' },
      hozAlign: 'left',
      minWidth: 120,
      widthGrow: 1,
      responsive: 0,
    },
    {
      title: 'Type',
      field: 'type',
      cssClass: 'dt-card-key',
      sorter: 'string',
      hozAlign: 'left',
      formatter: function (cell) {
        var type = cell.getValue();
        var typeClass = '';
        if (type === 'BUY') typeClass = 'buy';
        else if (type === 'SELL') typeClass = 'sell';
        else if (type === 'DIVIDEND') typeClass = 'dividend';
        else if (type === 'SPLIT') typeClass = 'split';
        return (
          '<span class="position-txn-type ' + typeClass + '">' + type + '</span>'
        );
      },
      minWidth: 115,
      widthGrow: 1,
      responsive: 0,
    },
    {
      title: 'Shares',
      field: 'shares',
      sorter: 'number',
      hozAlign: 'right',
      formatter: function (cell) {
        var val = cell.getValue();
        return val ? val.toLocaleString() : '—';
      },
      minWidth: 80,
      widthGrow: 1,
      responsive: 2,
    },
    {
      title: 'Price',
      field: 'price',
      sorter: 'number',
      hozAlign: 'right',
      formatter: function (cell) {
        var sym = cell.getRow().getData().currency_symbol || cs;
        return sym + cell.getValue().toFixed(2);
      },
      minWidth: 100,
      widthGrow: 1,
      responsive: 1,
    },
    {
      title: 'Total',
      field: 'total',
      cssClass: 'dt-card-key',
      sorter: 'number',
      hozAlign: 'right',
      formatter: function (cell) {
        var sym = cell.getRow().getData().currency_symbol || cs;
        return (
          '<strong>' +
          sym +
          cell.getValue().toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          }) +
          '</strong>'
        );
      },
      minWidth: 140,
      widthGrow: 1.5,
      responsive: 0,
    },
    {
      title: 'Notes',
      field: 'notes',
      sorter: 'string',
      hozAlign: 'left',
      formatter: function (cell) {
        var notes = cell.getValue();
        if (!notes)
          return '<span class="position-text-muted">—</span>';
        if (notes.length > 25) {
          return (
            '<span title="' + notes + '">' +
            notes.substring(0, 25) + '...</span>'
          );
        }
        return notes;
      },
      minWidth: 100,
      widthGrow: 2,
      responsive: 3,
    },
    {
      title: '',
      field: 'id',
      cssClass: 'dt-card-actions',
      headerSort: false,
      hozAlign: 'center',
      formatter: function (cell) {
        var id = cell.getValue();
        return (
          '<a href="/portfolio/transaction/' + id +
          '/edit" class="position-link-btn" title="Edit" aria-label="Edit">' +
          '<i class="bi bi-pencil"></i><span class="dt-action-label"> Edit</span></a>'
        );
      },
      minWidth: 50,
      widthGrow: 0.5,
      responsive: 0,
    },
  ];
}

/**
 * TransactionsTable — React island that wraps a Tabulator table for
 * portfolio transaction history.
 *
 * Tabulator is loaded via CDN (not bundled). This component creates a
 * Tabulator instance inside the mount point and cleans it up on unmount.
 *
 * Props:
 *   transactions: Array of { id, date, type, shares, price, total, currency_symbol, notes }
 *   currencySymbol: string (default: '$')
 */
export function TransactionsTable({ transactions, currencySymbol = '$' }) {
  const containerRef = useRef(null);
  const tabulatorRef = useRef(null);
  // createDataTable finds the table by selector, so it needs an id.
  const tableId = useRef(`txn-${Math.random().toString(36).slice(2, 9)}`);

  useEffect(() => {
    if (!transactions || !transactions.length) return;
    if (typeof Tabulator === 'undefined') return;
    if (!containerRef.current) return;

    tabulatorRef.current = createDataTable(`#${tableId.current}`, {
      data: transactions,
      columns: transactionColumns(currencySymbol),
      customConfig: {
        layout: 'fitColumns',
        pagination: false,
        layoutColumnsOnNewData: true,
        initialSort: [{ column: 'date', dir: 'desc' }],
      },
      mobileCards: true,
      foldColumns: true,
    });

    return () => {
      if (tabulatorRef.current) {
        tabulatorRef.current.destroy();
        tabulatorRef.current = null;
      }
    };
  }, [transactions, currencySymbol]);

  if (!transactions || !transactions.length) {
    return null;
  }

  return <div id={tableId.current} ref={containerRef} />;
}
