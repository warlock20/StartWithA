import { useRef, useEffect } from 'react';
import { createDataTable } from '../../lib/dataTable';

/**
 * React wrapper around Tabulator via createDataTable().
 *
 * Manages the Tabulator lifecycle (create on mount, destroy on unmount)
 * using useRef + useEffect — same pattern as the BlockNote editor wrapper.
 *
 * @param {object}   props
 * @param {string}   props.id          - DOM id for the table element (default: auto-generated)
 * @param {Array}    props.columns     - Tabulator column definitions (required)
 * @param {Array}    [props.data]      - Static row data
 * @param {string}   [props.ajaxURL]   - Remote data URL (alternative to data)
 * @param {Function} [props.ajaxResponse] - Transform AJAX response
 * @param {boolean}  [props.headerFilters] - Enable column header filters
 * @param {Function} [props.rowFormatter]  - Custom row formatter
 * @param {Function} [props.rowClick]      - Row click handler
 * @param {Function} [props.onTableReady]  - Called with Tabulator instance after build
 * @param {object}   [props.exportButtons] - Enable export buttons (csv/xlsx/json)
 * @param {object}   [props.exportConfig]  - Export config (filename, sheetName)
 * @param {object}   [props.customConfig]  - Additional Tabulator config overrides
 * @param {string}   [props.className]     - Extra CSS classes on the wrapper div
 */
export function DataTable({
  id,
  columns,
  data,
  ajaxURL,
  ajaxResponse,
  headerFilters,
  rowFormatter,
  rowClick,
  onTableReady,
  exportButtons,
  exportConfig,
  customConfig,
  className,
}) {
  const containerRef = useRef(null);
  const tableRef = useRef(null);
  const tableId = useRef(id || `dt-${Math.random().toString(36).slice(2, 9)}`);

  // Create table on mount, destroy on unmount
  useEffect(() => {
    if (!containerRef.current || !columns) return;

    const table = createDataTable(`#${tableId.current}`, {
      columns,
      data,
      ajaxURL,
      ajaxResponse,
      headerFilters,
      rowFormatter,
      rowClick,
      exportButtons,
      exportConfig,
      customConfig,
    });

    tableRef.current = table;
    if (table && onTableReady) onTableReady(table);

    return () => {
      if (tableRef.current) {
        tableRef.current.destroy();
        tableRef.current = null;
      }
    };
  }, []); // mount/unmount only — data updates go through tableRef

  // Update data when props.data changes (after initial mount)
  useEffect(() => {
    if (tableRef.current && data) {
      tableRef.current.replaceData(data);
    }
  }, [data]);

  return (
    <div className={`data-table-wrapper${className ? ` ${className}` : ''}`}>
      {exportButtons && <div className="data-table-controls" />}
      <div id={tableId.current} ref={containerRef} />
    </div>
  );
}
