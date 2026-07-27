/**
 * Portfolio Dashboard — React island entry point.
 *
 * Exposes:
 *   window.initCompositionStrip(elementId, config) — composition bar in header card
 *   window.initPortfolioDashboard(elementId, config) — main table + charts layout
 */
import { mountIsland } from './lib/mountIsland';
import { CompositionStripIsland } from './components/portfolio-dashboard/CompositionStripIsland';
import { PortfolioDashboard } from './components/portfolio-dashboard/PortfolioDashboard';

window.initCompositionStrip = function (elementId, config) {
  return mountIsland(elementId, CompositionStripIsland, config);
};

window.initPortfolioDashboard = function (elementId, config) {
  return mountIsland(elementId, PortfolioDashboard, config);
};
