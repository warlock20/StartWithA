import { mountIsland } from './lib/mountIsland';
import { TabRouter } from './components/company-dashboard/TabRouter';

/**
 * Company Dashboard Tabs — React island entry.
 *
 * Exposes `window.initCompanyDashboardTabs(elementId, config)`.
 * Config: { items: Array<{ type, key, label, icon, count, auto }> }
 */
window.initCompanyDashboardTabs = function (elementId, config) {
  return mountIsland(elementId, TabRouter, config);
};
