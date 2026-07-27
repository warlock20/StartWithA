import { mountIsland } from './lib/mountIsland';
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
  return mountIsland(elementId, SessionSummary, { config });
};
