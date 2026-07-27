import { mountIsland } from './lib/mountIsland';
import { StandaloneQA } from './components/company-dashboard/StandaloneQA';

window.initStandaloneQA = function (elementId, config) {
  return mountIsland(elementId, StandaloneQA, config);
};
