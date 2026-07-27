import { mountIsland } from './lib/mountIsland';
import { InsightsVelocityChart, InsightsSourcesChart } from './components/analytics/InsightsCharts';
import { SectorDonutChart } from './components/analytics/CocCharts';

/**
 * Analytics Charts — React island entry point.
 *
 * Exposes per-chart init functions for the redesigned analytics dashboard.
 * Each renders Recharts components into the corresponding mount point.
 */

/* ── Insights tab ── */

window.initInsightsVelocityChart = function (elementId, config) {
  return mountIsland(elementId, InsightsVelocityChart, config);
};

window.initInsightsSourcesChart = function (elementId, config) {
  return mountIsland(elementId, InsightsSourcesChart, config);
};

/* ── Circle of Competence tab ── */

window.initSectorDonutChart = function (elementId, config) {
  return mountIsland(elementId, SectorDonutChart, config);
};
