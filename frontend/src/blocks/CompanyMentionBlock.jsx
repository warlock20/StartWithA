import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";

/**
 * Custom Company Mention Block
 * For tagging and linking to companies in research notes
 */
export const CompanyMentionBlock = createReactBlockSpec(
  {
    type: "companyMention",
    propSchema: {
      ...defaultProps,
      companyId: {
        default: "",
      },
      companyName: {
        default: "",
      },
      ticker: {
        default: "",
      },
    },
    content: "inline",
  },
  {
    render: (props) => {
      const { companyId, companyName, ticker } = props.block.props;

      return (
        <div
          className="bn-company-mention-block"
          style={{
            border: "1px solid #dbeafe",
            borderLeft: "4px solid #3b82f6",
            padding: "10px 14px",
            margin: "8px 0",
            backgroundColor: "#eff6ff",
            borderRadius: "4px",
            cursor: "pointer",
          }}
          onClick={() => {
            if (companyId) {
              window.location.href = `/companies/${companyId}`;
            }
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "20px" }}>🏢</span>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    fontSize: "14px",
                    fontWeight: 600,
                    color: "#1e40af",
                  }}
                  contentEditable
                  suppressContentEditableWarning
                  onBlur={(e) => {
                    props.editor.updateBlock(props.block, {
                      props: { companyName: e.target.textContent },
                    });
                  }}
                >
                  {companyName || "Company name..."}
                </span>
                {ticker && (
                  <span
                    style={{
                      fontSize: "12px",
                      color: "#64748b",
                      backgroundColor: "#e0e7ff",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      fontWeight: 500,
                    }}
                  >
                    {ticker}
                  </span>
                )}
              </div>
              <div
                style={{
                  marginTop: "6px",
                  fontSize: "13px",
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
      const { companyId, companyName, ticker } = props.block.props;
      return (
        <div className="company-mention" data-company-id={companyId}>
          <strong>{companyName}</strong>
          {ticker && <span className="ticker">({ticker})</span>}
          <div>{props.contentRef}</div>
        </div>
      );
    },
  }
);
