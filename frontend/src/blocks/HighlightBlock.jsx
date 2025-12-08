import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";

/**
 * Custom Highlight Block
 * For highlighting key insights and important findings
 */
export const HighlightBlock = createReactBlockSpec(
  {
    type: "highlight",
    propSchema: {
      ...defaultProps,
      color: {
        default: "yellow",
        values: ["yellow", "green", "blue", "red", "purple"],
      },
      importance: {
        default: "normal",
        values: ["normal", "high", "critical"],
      },
    },
    content: "inline",
  },
  {
    render: (props) => {
      const { color, importance } = props.block.props;

      const colorStyles = {
        yellow: { bg: "#fef3c7", border: "#f59e0b", icon: "💡" },
        green: { bg: "#d1fae5", border: "#10b981", icon: "✅" },
        blue: { bg: "#dbeafe", border: "#3b82f6", icon: "ℹ️" },
        red: { bg: "#fee2e2", border: "#ef4444", icon: "⚠️" },
        purple: { bg: "#f3e8ff", border: "#a855f7", icon: "⭐" },
      };

      const style = colorStyles[color] || colorStyles.yellow;

      const importanceIcons = {
        normal: "",
        high: "❗",
        critical: "🔥",
      };

      return (
        <div
          className="bn-highlight-block"
          style={{
            border: `1px solid ${style.border}`,
            borderLeft: `4px solid ${style.border}`,
            padding: "12px 16px",
            margin: "8px 0",
            backgroundColor: style.bg,
            borderRadius: "4px",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "18px" }}>
              {style.icon} {importanceIcons[importance]}
            </span>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: importance === "critical" ? 600 : 500,
                  color: "#1e293b",
                  lineHeight: "1.6",
                }}
              >
                {props.contentRef}
              </div>
            </div>
            <div style={{ display: "flex", gap: "4px" }}>
              {["yellow", "green", "blue", "red", "purple"].map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    props.editor.updateBlock(props.block, {
                      props: { color: c },
                    });
                  }}
                  style={{
                    width: "20px",
                    height: "20px",
                    border: color === c ? "2px solid #000" : "1px solid #ccc",
                    borderRadius: "50%",
                    backgroundColor: colorStyles[c].bg,
                    cursor: "pointer",
                    padding: 0,
                  }}
                  title={c}
                />
              ))}
            </div>
          </div>
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { color, importance } = props.block.props;
      return (
        <div
          className={`highlight highlight-${color} highlight-${importance}`}
        >
          {props.contentRef}
        </div>
      );
    },
  }
);
