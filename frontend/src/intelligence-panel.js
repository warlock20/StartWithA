import { mountIsland } from './lib/mountIsland';
import { IntelligencePanel } from './components/intelligence-panel/IntelligencePanel';

/**
 * Intelligence Panel — React island entry.
 *
 * Mounts the IntelligencePanel component and exposes backward-compatible globals:
 *   - window.IntelligencePanel.syncWarnings(warnings) — called by template warnings code
 *   - window.IntelligencePanel.retry() — retry data fetch
 */
document.addEventListener('DOMContentLoaded', function () {
  mountIsland('intelligence-panel-mount', IntelligencePanel);
});
