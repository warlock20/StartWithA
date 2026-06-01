import { mountIsland } from "./lib/mountIsland";
import { DuplicateDetector } from "./components/DuplicateDetector";

/**
 * Mount the DuplicateDetector React island.
 *
 * Usage (in Jinja2 template):
 *   window.initDuplicateDetector('duplicate-alerts', {
 *     entityType: 'idea',
 *     nameInputId: 'idea-name',
 *     tickerInputId: 'idea-ticker',
 *     submitSelector: 'form[data-entity="idea"] button[type="submit"]'
 *   });
 */
window.initDuplicateDetector = function (elementId, config) {
  return mountIsland(elementId, DuplicateDetector, config);
};
