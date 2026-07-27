import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";
import React, { useState } from "react";

/**
 * Financial Metrics Block
 * Display key financial metrics in a beautiful card layout
 */
export const FinancialMetricsBlock = createReactBlockSpec(
  {
    type: "financialMetrics",
    propSchema: {
      ...defaultProps,
      companyName: { default: "" },
      revenue: { default: "" },
      revenueGrowth: { default: "" },
      netIncome: { default: "" },
      netMargin: { default: "" },
      pe: { default: "" },
      ps: { default: "" },
      debtToEquity: { default: "" },
      roe: { default: "" },
    },
    content: "none",
  },
  {
    render: (props) => {
      const [isEditing, setIsEditing] = useState(false);
      const { companyName, revenue, revenueGrowth, netIncome, netMargin, pe, ps, debtToEquity, roe } = props.block.props;

      const updateProp = (key, value) => {
        props.editor.updateBlock(props.block, {
          props: { [key]: value },
        });
      };

      const metrics = [
        { label: "Revenue", value: revenue, key: "revenue", icon: "💰" },
        { label: "Growth", value: revenueGrowth, key: "revenueGrowth", icon: "📈", color: parseFloat(revenueGrowth) > 0 ? "#10b981" : "#ef4444" },
        { label: "Net Income", value: netIncome, key: "netIncome", icon: "💵" },
        { label: "Net Margin", value: netMargin, key: "netMargin", icon: "📊" },
        { label: "P/E Ratio", value: pe, key: "pe", icon: "🎯" },
        { label: "P/S Ratio", value: ps, key: "ps", icon: "📉" },
        { label: "D/E Ratio", value: debtToEquity, key: "debtToEquity", icon: "⚖️" },
        { label: "ROE", value: roe, key: "roe", icon: "🎪", color: parseFloat(roe) > 15 ? "#10b981" : "#f59e0b" },
      ];

      return (
        <div
          className="bn-financial-metrics-block"
          style={{
            border: "2px solid #3b82f6",
            borderRadius: "12px",
            padding: "20px",
            margin: "16px 0",
            backgroundColor: "#f8fafc",
            boxShadow: "0 4px 6px rgba(0, 0, 0, 0.07)",
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "24px" }}>📊</span>
              {isEditing ? (
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => updateProp("companyName", e.target.value)}
                  placeholder="Company name..."
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    border: "1px solid #cbd5e1",
                    borderRadius: "4px",
                    padding: "4px 8px",
                    backgroundColor: "#fff",
                  }}
                  autoFocus
                />
              ) : (
                <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "#1e293b" }}>
                  {companyName || "Financial Metrics"}
                </h3>
              )}
            </div>
            <button
              onClick={() => setIsEditing(!isEditing)}
              style={{
                padding: "6px 12px",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                backgroundColor: "#fff",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 500,
              }}
            >
              {isEditing ? "Done" : "Edit"}
            </button>
          </div>

          {/* Metrics Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px",
            }}
          >
            {metrics.map((metric) => (
              <div
                key={metric.key}
                style={{
                  backgroundColor: "#fff",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
                  <span style={{ fontSize: "16px" }}>{metric.icon}</span>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                    {metric.label}
                  </span>
                </div>
                {isEditing ? (
                  <input
                    type="text"
                    value={metric.value}
                    onChange={(e) => updateProp(metric.key, e.target.value)}
                    placeholder="Value..."
                    style={{
                      width: "100%",
                      fontSize: "16px",
                      fontWeight: 600,
                      border: "1px solid #cbd5e1",
                      borderRadius: "4px",
                      padding: "4px 6px",
                    }}
                  />
                ) : (
                  <div
                    style={{
                      fontSize: "16px",
                      fontWeight: 700,
                      color: metric.color || "#1e293b",
                    }}
                  >
                    {metric.value || "-"}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Footer hint */}
          {!companyName && !isEditing && (
            <div style={{ marginTop: "12px", fontSize: "12px", color: "#94a3b8", textAlign: "center" }}>
              Click "Edit" to add financial metrics
            </div>
          )}
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { companyName, revenue, netIncome, pe } = props.block.props;
      return (
        <div className="financial-metrics">
          <h4>{companyName || "Financial Metrics"}</h4>
          <p>Revenue: {revenue} | Net Income: {netIncome} | P/E: {pe}</p>
        </div>
      );
    },
  }
);
