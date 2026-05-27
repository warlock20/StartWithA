import React from "react";
import { createRoot } from "react-dom/client";
import { SessionSummary } from "./components/session-summary/SessionSummary";

/**
 * Session Summary — React Island Entry Point
 *
 * Usage (in Jinja2 template):
 *   <div id="session-summary-root"></div>
 *   <script>
 *     window.initSessionSummary('session-summary-root', { ... });
 *   </script>
 */
window.initSessionSummary = function (elementId, config) {
  const container = document.getElementById(elementId);
  if (!container) {
    console.error(`Session Summary: element #${elementId} not found`);
    return null;
  }

  const root = createRoot(container);
  root.render(<SessionSummary config={config} />);
  return root;
};
