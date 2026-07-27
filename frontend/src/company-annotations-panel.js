import { mountIsland } from './lib/mountIsland';
import { CompanyAnnotationsPanel } from './components/company-dashboard/CompanyAnnotationsPanel';

window.initCompanyAnnotationsPanel = function (elementId, config) {
  return mountIsland(elementId, CompanyAnnotationsPanel, config);
};
