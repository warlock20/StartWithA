import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";
import React, { useState } from "react";

/**
 * Investment Thesis Block
 * Bull vs Bear case side-by-side comparison
 */
export const ThesisBlock = createReactBlockSpec(
  {
    type: "thesis",
    propSchema: {
      ...defaultProps,
      title: { default: "" },
      bullCase: { default: "" },
      bearCase: { default: "" },
      baseCase: { default: "" },
    },
    content: "none",
  },
  {
    render: (props) => {
      const [activeTab, setActiveTab] = useState("bull");
      const { title, bullCase, bearCase, baseCase } = props.block.props;

      const updateProp = (key, value) => {
        props.editor.updateBlock(props.block, {
          props: { [key]: value },
        });
      };

      const tabs = [
        { key: "bull", label: "🐂 Bull Case", color: "#10b981", content: bullCase },
        { key: "base", label: "📊 Base Case", color: "#3b82f6", content: baseCase },
        { key: "bear", label: "🐻 Bear Case", color: "#ef4444", content: bearCase },
      ];

      return (
        <div
          className="bn-thesis-block"
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
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              padding: "16px 20px",
              color: "#fff",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "24px" }}>💭</span>
              <input
                type="text"
                value={title}
                onChange={(e) => updateProp("title", e.target.value)}
                placeholder="Investment Thesis Title..."
                style={{
                  flex: 1,
                  fontSize: "18px",
                  fontWeight: 700,
                  backgroundColor: "transparent",
                  border: "none",
                  color: "#fff",
                  outline: "none",
                }}
              />
            </div>
          </div>

          {/* Tabs */}
          <div
            style={{
              display: "flex",
              borderBottom: "2px solid #e2e8f0",
              backgroundColor: "#f8fafc",
            }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  flex: 1,
                  padding: "12px 16px",
                  border: "none",
                  backgroundColor: activeTab === tab.key ? "#fff" : "transparent",
                  borderBottom: activeTab === tab.key ? `3px solid ${tab.color}` : "3px solid transparent",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: activeTab === tab.key ? tab.color : "#64748b",
                  transition: "all 0.2s",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div style={{ padding: "20px" }}>
            {tabs.map((tab) => (
              activeTab === tab.key && (
                <textarea
                  key={tab.key}
                  value={tab.content}
                  onChange={(e) => updateProp(tab.key === "bull" ? "bullCase" : tab.key === "bear" ? "bearCase" : "baseCase", e.target.value)}
                  placeholder={`Write your ${tab.label.split(" ")[1]} scenario here...

Examples:
- Key assumptions
- Growth drivers/risks
- Valuation implications
- Probability assessment`}
                  style={{
                    width: "100%",
                    minHeight: "200px",
                    border: `2px solid ${tab.color}20`,
                    borderRadius: "8px",
                    padding: "16px",
                    fontSize: "14px",
                    lineHeight: "1.6",
                    fontFamily: "inherit",
                    resize: "vertical",
                    outline: "none",
                    backgroundColor: `${tab.color}05`,
                  }}
                />
              )
            ))}
          </div>

          {/* Quick Stats */}
          <div
            style={{
              display: "flex",
              gap: "12px",
              padding: "12px 20px",
              backgroundColor: "#f8fafc",
              borderTop: "1px solid #e2e8f0",
              fontSize: "12px",
              color: "#64748b",
            }}
          >
            <div>
              <span style={{ fontWeight: 600 }}>Bull:</span> {bullCase.split("\n").filter(l => l.trim()).length} points
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Base:</span> {baseCase.split("\n").filter(l => l.trim()).length} points
            </div>
            <div>
              <span style={{ fontWeight: 600 }}>Bear:</span> {bearCase.split("\n").filter(l => l.trim()).length} points
            </div>
          </div>
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { title, bullCase, bearCase, baseCase } = props.block.props;
      return (
        <div className="thesis-block">
          <h4>{title || "Investment Thesis"}</h4>
          <div className="bull-case">
            <h5>Bull Case</h5>
            <p>{bullCase}</p>
          </div>
          <div className="base-case">
            <h5>Base Case</h5>
            <p>{baseCase}</p>
          </div>
          <div className="bear-case">
            <h5>Bear Case</h5>
            <p>{bearCase}</p>
          </div>
        </div>
      );
    },
  }
);
