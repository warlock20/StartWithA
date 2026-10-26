import { useEffect } from 'react';

/**
 * ChecklistInspector — Behavior-only bridge for the checklist tree inspector.
 * Returns null. Attaches click handlers to .checklist-tree items to populate
 * the inspector panel with item details, edit/delete/move URLs.
 *
 * Desktop (lg and up) swaps the add panel for the item panel in the right-hand
 * column. Below lg the item panel is an `offcanvas-lg` bottom sheet, so a tap
 * opens it over the list and the add panel is left alone.
 */
var DESKTOP_QUERY = '(min-width: 992px)';

export function ChecklistInspector() {
  useEffect(function () {
    var treeContainer = document.querySelector('.checklist-tree');
    var inspectorPanel = document.getElementById('inspector-panel');
    var overviewPanel = document.getElementById('inspector-overview');
    var contentPanel = document.getElementById('inspector-content');
    var closeBtn = document.getElementById('inspector-close-btn');

    if (!treeContainer || !inspectorPanel || !overviewPanel || !contentPanel) return;

    var editUrlTemplate = inspectorPanel.dataset.editUrlTemplate;
    var deleteUrlTemplate = inspectorPanel.dataset.deleteUrlTemplate;
    var moveUrlTemplate = inspectorPanel.dataset.moveUrlTemplate;

    function handleTreeClick(event) {
      var clickedItemLink = event.target.closest('.checklist-tree-item a');
      if (!clickedItemLink) return;
      event.preventDefault();
      clearActive();
      clickedItemLink.classList.add('active');
      populateInspector(clickedItemLink);
    }

    function isDesktop() {
      return window.matchMedia(DESKTOP_QUERY).matches;
    }

    function clearActive() {
      var currentActive = treeContainer.querySelector('a.active');
      if (currentActive) currentActive.classList.remove('active');
    }

    // On a phone the close button dismisses the sheet itself (data-bs-dismiss).
    function handleClose() {
      if (!isDesktop()) return;
      contentPanel.classList.add('d-none');
      overviewPanel.classList.remove('d-none');
      clearActive();
    }

    function handleSheetHidden(event) {
      if (event.target === contentPanel) clearActive();
    }

    function populateInspector(el) {
      var itemId = el.dataset.itemId;
      var itemText = el.dataset.itemText;
      var llmPrompt = el.dataset.llmPrompt;
      var isFirst = el.dataset.isFirst === 'True';
      var isLast = el.dataset.isLast === 'True';

      contentPanel.classList.remove('d-none');
      if (isDesktop()) {
        overviewPanel.classList.add('d-none');
      } else {
        window.bootstrap.Offcanvas.getOrCreateInstance(contentPanel).show();
      }

      contentPanel.querySelector('#inspector-item-text').textContent = itemText;
      var llmPromptDisplay = contentPanel.querySelector('#inspector-llm-prompt-display');
      var llmPromptText = contentPanel.querySelector('#inspector-llm-prompt');
      if (llmPrompt) {
        llmPromptText.textContent = llmPrompt;
        llmPromptDisplay.style.display = 'block';
      } else {
        llmPromptDisplay.style.display = 'none';
      }

      if (editUrlTemplate) {
        contentPanel.querySelector('#inspector-edit-btn').href = editUrlTemplate.replace('/0', '/' + itemId);
      }
      if (deleteUrlTemplate) {
        contentPanel.querySelector('#inspector-delete-form').action = deleteUrlTemplate.replace('/0', '/' + itemId);
      }
      if (moveUrlTemplate) {
        var moveUpUrl = moveUrlTemplate.replace('/0/', '/' + itemId + '/').replace('__DIRECTION__', 'up');
        var moveDownUrl = moveUrlTemplate.replace('/0/', '/' + itemId + '/').replace('__DIRECTION__', 'down');
        contentPanel.querySelector('#inspector-move-up-form').action = moveUpUrl;
        contentPanel.querySelector('#inspector-move-down-form').action = moveDownUrl;
      }

      // Hide the whole form (a flex-fill slot), not just the button, so the other one spans the row.
      contentPanel.querySelector('#inspector-move-up-form').style.display = isFirst ? 'none' : '';
      contentPanel.querySelector('#inspector-move-down-form').style.display = isLast ? 'none' : '';
      contentPanel.querySelector('#inspector-parent-id').value = itemId;
      var addUnderBtn = contentPanel.querySelector('#inspector-add-under');
      if (addUnderBtn) addUnderBtn.dataset.addUnder = itemId;
      contentPanel.querySelector('#inspector-subitem-text').value = '';
      contentPanel.querySelector('#inspector-subitem-llm').value = '';
    }

    treeContainer.addEventListener('click', handleTreeClick);
    if (closeBtn) closeBtn.addEventListener('click', handleClose);
    contentPanel.addEventListener('hidden.bs.offcanvas', handleSheetHidden);

    return function () {
      treeContainer.removeEventListener('click', handleTreeClick);
      if (closeBtn) closeBtn.removeEventListener('click', handleClose);
      contentPanel.removeEventListener('hidden.bs.offcanvas', handleSheetHidden);
    };
  }, []);

  return null;
}
