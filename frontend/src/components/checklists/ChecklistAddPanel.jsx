import { useEffect } from 'react';
import { initAddPanel } from './addPanel';

/**
 * ChecklistAddPanel — Behavior-only bridge for the edit page's add panel / sheet.
 * Returns null. See addPanel.js.
 */
export function ChecklistAddPanel() {
  useEffect(function () {
    return initAddPanel(document.getElementById('inspector-overview'));
  }, []);

  return null;
}
