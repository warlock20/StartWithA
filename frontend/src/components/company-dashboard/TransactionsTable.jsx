import { useEffect, useRef } from 'react';

/**
 * TransactionsTable — React island that wraps a Tabulator table for
 * portfolio transaction history.
 *
 * Tabulator is loaded via CDN (not bundled). This component creates a
 * Tabulator instance inside the mount point and cleans it up on unmount.
 *
 * Props:
 *   transactions: Array of { id, date, type, shares, price, total, notes }
 *   currencySymbol: string (default: '$')
 */
export function TransactionsTable({ transactions, currencySymbol = '$' }) {
  const containerRef = useRef(null);
  const tabulatorRef = useRef(null);

  useEffect(() => {
    if (!transactions || !transactions.length) return;
    if (typeof Tabulator === 'undefined') return;
    if (!containerRef.current) return;

    var cs = currencySymbol;

    tabulatorRef.current = new Tabulator(containerRef.current, {
      data: transactions,
      layout: 'fitColumns',
      responsiveLayout: 'collapse',
      pagination: false,
      layoutColumnsOnNewData: true,
      columns: [
        {
          title: 'Date',
          field: 'date',
          sorter: 'date',
          sorterParams: { format: 'yyyy-MM-dd' },
          hozAlign: 'left',
          minWidth: 100,
          widthGrow: 1,
        },
        {
          title: 'Type',
          field: 'type',
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
          minWidth: 90,
          widthGrow: 1,
        },
        {
          title: 'Shares',
          field: 'shares',
          sorter: 'number',
          hozAlign: 'right',
          formatter: function (cell) {
            var val = cell.getValue();
            return val ? val.toLocaleString() : '\u2014';
          },
          minWidth: 80,
          widthGrow: 1,
        },
        {
          title: 'Price',
          field: 'price',
          sorter: 'number',
          hozAlign: 'right',
          formatter: function (cell) {
            return cs + cell.getValue().toFixed(2);
          },
          minWidth: 90,
          widthGrow: 1,
        },
        {
          title: 'Total',
          field: 'total',
          sorter: 'number',
          hozAlign: 'right',
          formatter: function (cell) {
            return (
              '<strong>' +
              cs +
              cell.getValue().toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }) +
              '</strong>'
            );
          },
          minWidth: 100,
          widthGrow: 1.5,
        },
        {
          title: 'Notes',
          field: 'notes',
          sorter: 'string',
          hozAlign: 'left',
          formatter: function (cell) {
            var notes = cell.getValue();
            if (!notes)
              return '<span class="position-text-muted">\u2014</span>';
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
        },
        {
          title: '',
          field: 'id',
          headerSort: false,
          hozAlign: 'center',
          formatter: function (cell) {
            var id = cell.getValue();
            return (
              '<a href="/portfolio/transaction/' + id +
              '/edit" class="position-link-btn" title="Edit">' +
              '<i class="bi bi-pencil"></i></a>'
            );
          },
          minWidth: 50,
          widthGrow: 0.5,
        },
      ],
      initialSort: [{ column: 'date', dir: 'desc' }],
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

  return <div ref={containerRef} />;
}
