import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";
import React, { useState } from "react";

/**
 * Data Table Block
 * Sortable tables with inline mini charts and formatting
 */
export const DataTableBlock = createReactBlockSpec(
  {
    type: "dataTable",
    propSchema: {
      ...defaultProps,
      title: { default: "" },
      headers: { default: JSON.stringify(["Column 1", "Column 2", "Column 3"]) },
      rows: { default: JSON.stringify([
        ["", "", ""],
        ["", "", ""],
      ]) },
      columnTypes: { default: JSON.stringify(["text", "text", "text"]) }, // text, number, percentage, currency
    },
    content: "none",
  },
  {
    render: (props) => {
      const [isEditing, setIsEditing] = useState(false);
      const [sortConfig, setSortConfig] = useState({ column: null, direction: null });
      const { title } = props.block.props;

      // Parse JSON props
      const headers = JSON.parse(props.block.props.headers || '["Column 1", "Column 2", "Column 3"]');
      const rows = JSON.parse(props.block.props.rows || '[["", "", ""], ["", "", ""]]');
      const columnTypes = JSON.parse(props.block.props.columnTypes || '["text", "text", "text"]');

      const updateProp = (key, value) => {
        props.editor.updateBlock(props.block, {
          props: { [key]: typeof value === 'string' ? value : JSON.stringify(value) },
        });
      };

      const addRow = () => {
        const newRow = new Array(headers.length).fill("");
        updateProp("rows", [...rows, newRow]);
      };

      const addColumn = () => {
        updateProp("headers", [...headers, `Column ${headers.length + 1}`]);
        updateProp("rows", rows.map(row => [...row, ""]));
        updateProp("columnTypes", [...columnTypes, "text"]);
      };

      const deleteRow = (index) => {
        if (rows.length > 1) {
          updateProp("rows", rows.filter((_, i) => i !== index));
        }
      };

      const deleteColumn = (index) => {
        if (headers.length > 1) {
          updateProp("headers", headers.filter((_, i) => i !== index));
          updateProp("rows", rows.map(row => row.filter((_, i) => i !== index)));
          updateProp("columnTypes", columnTypes.filter((_, i) => i !== index));
        }
      };

      const updateCell = (rowIndex, colIndex, value) => {
        const newRows = [...rows];
        newRows[rowIndex][colIndex] = value;
        updateProp("rows", newRows);
      };

      const updateHeader = (index, value) => {
        const newHeaders = [...headers];
        newHeaders[index] = value;
        updateProp("headers", newHeaders);
      };

      const updateColumnType = (index, type) => {
        const newTypes = [...columnTypes];
        newTypes[index] = type;
        updateProp("columnTypes", newTypes);
      };

      const handleSort = (columnIndex) => {
        let direction = "asc";
        if (sortConfig.column === columnIndex && sortConfig.direction === "asc") {
          direction = "desc";
        }
        setSortConfig({ column: columnIndex, direction });
      };

      const getSortedRows = () => {
        if (sortConfig.column === null) return rows;

        const sorted = [...rows].sort((a, b) => {
          const aVal = a[sortConfig.column];
          const bVal = b[sortConfig.column];
          const colType = columnTypes[sortConfig.column];

          if (colType === "number" || colType === "percentage" || colType === "currency") {
            const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, "")) || 0;
            const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, "")) || 0;
            return sortConfig.direction === "asc" ? aNum - bNum : bNum - aNum;
          }

          return sortConfig.direction === "asc"
            ? String(aVal).localeCompare(String(bVal))
            : String(bVal).localeCompare(String(aVal));
        });

        return sorted;
      };

      const formatCellValue = (value, type) => {
        if (!value) return value;

        switch (type) {
          case "currency":
            const num = parseFloat(value.replace(/[^0-9.-]/g, ""));
            return isNaN(num) ? value : `$${num.toLocaleString()}`;
          case "percentage":
            const pct = parseFloat(value.replace(/[^0-9.-]/g, ""));
            return isNaN(pct) ? value : `${pct}%`;
          case "number":
            const n = parseFloat(value.replace(/[^0-9.-]/g, ""));
            return isNaN(n) ? value : n.toLocaleString();
          default:
            return value;
        }
      };

      const getMiniChart = (columnIndex) => {
        const values = rows
          .map(row => parseFloat(row[columnIndex]?.replace(/[^0-9.-]/g, "")))
          .filter(v => !isNaN(v));

        if (values.length === 0) return null;

        const max = Math.max(...values);
        const min = Math.min(...values);
        const range = max - min;

        return (
          <div style={{ display: "flex", gap: "1px", height: "20px", alignItems: "flex-end" }}>
            {values.map((val, i) => {
              const height = range === 0 ? 50 : ((val - min) / range) * 100;
              return (
                <div
                  key={i}
                  style={{
                    width: "4px",
                    height: `${height}%`,
                    backgroundColor: val >= 0 ? "#10b981" : "#ef4444",
                    borderRadius: "2px",
                  }}
                />
              );
            })}
          </div>
        );
      };

      return (
        <div
          className="bn-data-table-block"
          style={{
            border: "2px solid #e2e8f0",
            borderRadius: "12px",
            overflow: "hidden",
            margin: "16px 0",
            backgroundColor: "#fff",
            boxShadow: "0 4px 6px rgba(0, 0, 0, 0.05)",
          }}
        >
          {/* Header */}
          <div
            style={{
              background: "linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)",
              padding: "16px 20px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "24px" }}>📊</span>
              {isEditing ? (
                <input
                  type="text"
                  value={title}
                  onChange={(e) => updateProp("title", e.target.value)}
                  placeholder="Table Title..."
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    backgroundColor: "transparent",
                    border: "none",
                    color: "#fff",
                    outline: "none",
                  }}
                />
              ) : (
                <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "#fff" }}>
                  {title || "Data Table"}
                </h3>
              )}
            </div>
            <button
              onClick={() => setIsEditing(!isEditing)}
              style={{
                padding: "6px 12px",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                borderRadius: "6px",
                backgroundColor: "rgba(255, 255, 255, 0.2)",
                color: "#fff",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              {isEditing ? "Done" : "Edit"}
            </button>
          </div>

          {/* Table */}
          <div style={{ overflowX: "auto", padding: "20px" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "14px",
              }}
            >
              <thead>
                <tr>
                  {headers.map((header, index) => (
                    <th
                      key={index}
                      onClick={() => handleSort(index)}
                      style={{
                        padding: "12px",
                        textAlign: "left",
                        borderBottom: "2px solid #e2e8f0",
                        backgroundColor: "#f8fafc",
                        fontWeight: 600,
                        color: "#1e293b",
                        cursor: "pointer",
                        position: "relative",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {isEditing ? (
                          <input
                            type="text"
                            value={header}
                            onChange={(e) => updateHeader(index, e.target.value)}
                            style={{
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                              padding: "4px 8px",
                              fontSize: "14px",
                            }}
                          />
                        ) : (
                          <span>{header}</span>
                        )}
                        {sortConfig.column === index && (
                          <span>{sortConfig.direction === "asc" ? "↑" : "↓"}</span>
                        )}
                        {isEditing && (
                          <>
                            <select
                              value={columnTypes[index]}
                              onChange={(e) => updateColumnType(index, e.target.value)}
                              style={{
                                fontSize: "11px",
                                padding: "2px 4px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                              }}
                            >
                              <option value="text">Text</option>
                              <option value="number">Number</option>
                              <option value="currency">Currency</option>
                              <option value="percentage">Percentage</option>
                            </select>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteColumn(index);
                              }}
                              style={{
                                fontSize: "12px",
                                padding: "2px 6px",
                                border: "none",
                                background: "#ef4444",
                                color: "#fff",
                                borderRadius: "4px",
                                cursor: "pointer",
                              }}
                            >
                              ×
                            </button>
                          </>
                        )}
                      </div>
                      {/* Mini chart for number columns */}
                      {(columnTypes[index] === "number" ||
                        columnTypes[index] === "currency" ||
                        columnTypes[index] === "percentage") &&
                        !isEditing && (
                          <div style={{ marginTop: "8px" }}>
                            {getMiniChart(index)}
                          </div>
                        )}
                    </th>
                  ))}
                  {isEditing && (
                    <th style={{ width: "50px", backgroundColor: "#f8fafc" }}>
                      <button
                        onClick={addColumn}
                        style={{
                          padding: "4px 8px",
                          border: "none",
                          background: "#3b82f6",
                          color: "#fff",
                          borderRadius: "4px",
                          cursor: "pointer",
                          fontSize: "12px",
                        }}
                      >
                        + Col
                      </button>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {getSortedRows().map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    style={{
                      borderBottom: "1px solid #f1f5f9",
                    }}
                  >
                    {row.map((cell, colIndex) => (
                      <td
                        key={colIndex}
                        style={{
                          padding: "12px",
                          color: "#334155",
                        }}
                      >
                        {isEditing ? (
                          <input
                            type="text"
                            value={cell}
                            onChange={(e) => updateCell(rowIndex, colIndex, e.target.value)}
                            style={{
                              width: "100%",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                              padding: "6px 8px",
                              fontSize: "14px",
                            }}
                          />
                        ) : (
                          formatCellValue(cell, columnTypes[colIndex])
                        )}
                      </td>
                    ))}
                    {isEditing && (
                      <td>
                        <button
                          onClick={() => deleteRow(rowIndex)}
                          style={{
                            padding: "4px 8px",
                            border: "none",
                            background: "#ef4444",
                            color: "#fff",
                            borderRadius: "4px",
                            cursor: "pointer",
                            fontSize: "12px",
                          }}
                        >
                          ×
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Add Row Button */}
            {isEditing && (
              <button
                onClick={addRow}
                style={{
                  marginTop: "12px",
                  padding: "8px 16px",
                  border: "1px solid #cbd5e1",
                  background: "#fff",
                  color: "#3b82f6",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: 600,
                }}
              >
                + Add Row
              </button>
            )}
          </div>

          {/* Stats Footer */}
          {!isEditing && (
            <div
              style={{
                padding: "12px 20px",
                backgroundColor: "#f8fafc",
                borderTop: "1px solid #e2e8f0",
                fontSize: "12px",
                color: "#64748b",
                display: "flex",
                gap: "16px",
              }}
            >
              <span><strong>{rows.length}</strong> rows</span>
              <span><strong>{headers.length}</strong> columns</span>
              <span>Click headers to sort</span>
            </div>
          )}
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { title } = props.block.props;
      const headers = JSON.parse(props.block.props.headers || '[]');
      const rows = JSON.parse(props.block.props.rows || '[]');

      return (
        <div className="data-table">
          <h4>{title || "Data Table"}</h4>
          <table>
            <thead>
              <tr>
                {headers.map((h, i) => <th key={i}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => <td key={j}>{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    },
  }
);
