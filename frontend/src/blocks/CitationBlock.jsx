import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";

/**
 * Custom Citation Block
 * For adding citations and references in research notes
 */
export const CitationBlock = createReactBlockSpec(
  {
    type: "citation",
    propSchema: {
      ...defaultProps,
      source: {
        default: "",
      },
      url: {
        default: "",
      },
      accessDate: {
        default: "",
      },
    },
    content: "inline",
  },
  {
    render: (props) => {
      const { source, url, accessDate } = props.block.props;

      return (
        <div
          className="bn-citation-block"
          style={{
            border: "1px solid #e2e8f0",
            borderLeft: "4px solid #3b82f6",
            padding: "12px 16px",
            margin: "8px 0",
            backgroundColor: "#f8fafc",
            borderRadius: "4px",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
            <span style={{ fontSize: "20px", opacity: 0.6 }}>📚</span>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#1e293b",
                  marginBottom: "4px",
                }}
                contentEditable
                suppressContentEditableWarning
                onBlur={(e) => {
                  props.editor.updateBlock(props.block, {
                    props: { source: e.target.textContent },
                  });
                }}
              >
                {source || "Citation source..."}
              </div>
              {url && (
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: "12px",
                    color: "#3b82f6",
                    textDecoration: "none",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {url}
                </a>
              )}
              {accessDate && (
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  Accessed: {accessDate}
                </div>
              )}
              <div
                style={{
                  marginTop: "8px",
                  fontSize: "14px",
                  color: "#475569",
                }}
              >
                {props.contentRef}
              </div>
            </div>
          </div>
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { source, url, accessDate } = props.block.props;
      return (
        <blockquote className="citation">
          <strong>{source}</strong>
          {url && <a href={url}>{url}</a>}
          {accessDate && <small>Accessed: {accessDate}</small>}
          <div>{props.contentRef}</div>
        </blockquote>
      );
    },
  }
);
