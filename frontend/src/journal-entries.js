import { mountIsland } from './lib/mountIsland';
import { JournalEntries } from './components/company-dashboard/JournalEntries';

window.initJournalEntries = function (elementId, config) {
  return mountIsland(elementId, JournalEntries, config);
};
