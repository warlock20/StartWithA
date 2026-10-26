import { mountIsland } from './lib/mountIsland';
import { ChecklistInspector } from './components/checklists/ChecklistInspector';
import { ChecklistAddPanel } from './components/checklists/ChecklistAddPanel';

function ChecklistEditor() {
  return (
    <>
      <ChecklistInspector />
      <ChecklistAddPanel />
    </>
  );
}

window.initChecklistInspector = function (elementId) {
  return mountIsland(elementId, ChecklistEditor, {});
};
