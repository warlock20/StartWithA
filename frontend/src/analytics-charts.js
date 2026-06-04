import { mountIsland } from './lib/mountIsland';
import { OverviewActivityChart } from './components/analytics/OverviewActivityChart';
import { TimeAnalysisCharts } from './components/analytics/TimeAnalysisCharts';
import { SourceFunnelChart } from './components/analytics/SourceFunnelChart';
import { PatternsCharts } from './components/analytics/PatternsCharts';
import { CocCharts } from './components/analytics/CocCharts';

/**
 * Analytics Charts — React island entry point.
 *
 * Exposes per-tab init functions. Each renders Recharts components
 * into the corresponding tab's mount point.
 */

window.initOverviewChart = function (elementId, config) {
  return mountIsland(elementId, OverviewActivityChart, config);
};

window.initTimeAnalysisCharts = function (elementId, config) {
  return mountIsland(elementId, TimeAnalysisCharts, config);
};

window.initSourceFunnelChart = function (elementId, config) {
  return mountIsland(elementId, SourceFunnelChart, config);
};

window.initPatternsCharts = function (elementId, config) {
  return mountIsland(elementId, PatternsCharts, config);
};

window.initCocCharts = function (elementId, config) {
  return mountIsland(elementId, CocCharts, config);
};
