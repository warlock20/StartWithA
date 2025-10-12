import { createReactBlockSpec } from "@blocknote/react";
import { defaultProps } from "@blocknote/core";
import React, { useState } from "react";

/**
 * Embed Block
 * Embed YouTube videos, tweets, charts, and more
 */
export const EmbedBlock = createReactBlockSpec(
  {
    type: "embed",
    propSchema: {
      ...defaultProps,
      url: { default: "" },
      embedType: { default: "auto" }, // auto, youtube, twitter, tradingview, iframe
      caption: { default: "" },
    },
    content: "none",
  },
  {
    render: (props) => {
      const [isEditing, setIsEditing] = useState(!props.block.props.url);
      const { url, embedType, caption } = props.block.props;

      const updateProp = (key, value) => {
        props.editor.updateBlock(props.block, {
          props: { [key]: value },
        });
      };

      const detectEmbedType = (url) => {
        if (!url) return "iframe";
        if (url.includes("youtube.com") || url.includes("youtu.be")) return "youtube";
        if (url.includes("twitter.com") || url.includes("x.com")) return "twitter";
        if (url.includes("tradingview.com")) return "tradingview";
        return "iframe";
      };

      const getYouTubeId = (url) => {
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
        const match = url.match(regExp);
        return match && match[2].length === 11 ? match[2] : null;
      };

      const getTweetId = (url) => {
        const match = url.match(/status\/(\d+)/);
        return match ? match[1] : null;
      };

      const renderEmbed = () => {
        const type = embedType === "auto" ? detectEmbedType(url) : embedType;

        switch (type) {
          case "youtube": {
            const videoId = getYouTubeId(url);
            if (!videoId) return renderError("Invalid YouTube URL");
            return (
              <iframe
                width="100%"
                height="400"
                src={`https://www.youtube.com/embed/${videoId}`}
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                style={{ borderRadius: "8px" }}
              />
            );
          }

          case "twitter": {
            const tweetId = getTweetId(url);
            if (!tweetId) return renderError("Invalid Twitter URL");
            return (
              <div style={{ maxWidth: "550px", margin: "0 auto" }}>
                <blockquote className="twitter-tweet" data-theme="light">
                  <a href={url}>Loading tweet...</a>
                </blockquote>
                <script async src="https://platform.twitter.com/widgets.js" charSet="utf-8"></script>
              </div>
            );
          }

          case "tradingview":
            return (
              <iframe
                src={url}
                width="100%"
                height="500"
                frameBorder="0"
                allowTransparency="true"
                scrolling="no"
                style={{ borderRadius: "8px" }}
              />
            );

          case "iframe":
          default:
            return (
              <iframe
                src={url}
                width="100%"
                height="500"
                frameBorder="0"
                style={{ borderRadius: "8px", border: "1px solid #e2e8f0" }}
              />
            );
        }
      };

      const renderError = (message) => (
        <div style={{ padding: "40px", textAlign: "center", color: "#ef4444" }}>
          <span style={{ fontSize: "48px" }}>⚠️</span>
          <p>{message}</p>
        </div>
      );

      return (
        <div
          className="bn-embed-block"
          style={{
            border: "2px solid #e2e8f0",
            borderRadius: "12px",
            overflow: "hidden",
            margin: "16px 0",
            backgroundColor: "#fff",
          }}
        >
          {isEditing ? (
            <div style={{ padding: "20px" }}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "14px", fontWeight: 600, marginBottom: "8px", color: "#475569" }}>
                  🔗 Embed URL
                </label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => updateProp("url", e.target.value)}
                  placeholder="Paste YouTube, Twitter, TradingView, or any URL..."
                  style={{
                    width: "100%",
                    padding: "12px",
                    border: "2px solid #cbd5e1",
                    borderRadius: "8px",
                    fontSize: "14px",
                    outline: "none",
                  }}
                  autoFocus
                />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "14px", fontWeight: 600, marginBottom: "8px", color: "#475569" }}>
                  Caption (optional)
                </label>
                <input
                  type="text"
                  value={caption}
                  onChange={(e) => updateProp("caption", e.target.value)}
                  placeholder="Add a caption..."
                  style={{
                    width: "100%",
                    padding: "12px",
                    border: "2px solid #cbd5e1",
                    borderRadius: "8px",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <button
                onClick={() => setIsEditing(false)}
                disabled={!url}
                style={{
                  padding: "10px 20px",
                  backgroundColor: url ? "#3b82f6" : "#cbd5e1",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: url ? "pointer" : "not-allowed",
                  fontWeight: 600,
                  fontSize: "14px",
                }}
              >
                Embed Content
              </button>
            </div>
          ) : (
            <>
              <div style={{ position: "relative" }}>
                {renderEmbed()}
                <button
                  onClick={() => setIsEditing(true)}
                  style={{
                    position: "absolute",
                    top: "10px",
                    right: "10px",
                    padding: "6px 12px",
                    backgroundColor: "rgba(255, 255, 255, 0.9)",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: 600,
                  }}
                >
                  ✏️ Edit
                </button>
              </div>
              {caption && (
                <div
                  style={{
                    padding: "12px 20px",
                    backgroundColor: "#f8fafc",
                    borderTop: "1px solid #e2e8f0",
                    fontSize: "14px",
                    color: "#64748b",
                    fontStyle: "italic",
                  }}
                >
                  {caption}
                </div>
              )}
            </>
          )}
        </div>
      );
    },
    toExternalHTML: (props) => {
      const { url, caption } = props.block.props;
      return (
        <div className="embed-block">
          <iframe src={url} width="100%" height="500" frameBorder="0"></iframe>
          {caption && <p className="caption">{caption}</p>}
        </div>
      );
    },
  }
);
