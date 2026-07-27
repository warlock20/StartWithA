import { mountIsland } from './lib/mountIsland';
import { ChecklistInspector } from './components/checklists/ChecklistInspector';

window.initChecklistInspector = function (elementId) {
  return mountIsland(elementId, ChecklistInspector, {});
};
