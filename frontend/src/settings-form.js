import { mountIsland } from './lib/mountIsland';
import { SettingsForm } from './components/company-dashboard/SettingsForm';

window.initSettingsForm = function (elementId, config) {
  return mountIsland(elementId, SettingsForm, config);
};
