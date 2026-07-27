import { mountIsland } from './lib/mountIsland';
import { SecFilingsFetcher } from './components/company-dashboard/SecFilingsFetcher';

window.initSecFilingsFetcher = function (elementId, config) {
  return mountIsland(elementId, SecFilingsFetcher, config);
};
