import { useEffect } from 'react';

/**
 * ChecklistInspector — Behavior-only bridge for the checklist tree inspector.
 * Returns null. Attaches click handlers to .checklist-tree items to populate
 * the inspector panel with item details, edit/delete/move URLs.
 */
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
      var currentActive = treeContainer.querySelector('a.active');
      if (currentActive) currentActive.classList.remove('active');
      clickedItemLink.classList.add('active');
      populateInspector(clickedItemLink);
    }

    function handleClose() {
      contentPanel.classList.add('d-none');
      overviewPanel.classList.remove('d-none');
      var currentActive = treeContainer.querySelector('a.active');
      if (currentActive) currentActive.classList.remove('active');
    }

    function populateInspector(el) {
      var itemId = el.dataset.itemId;
      var itemText = el.dataset.itemText;
      var llmPrompt = el.dataset.llmPrompt;
      var isFirst = el.dataset.isFirst === 'True';
      var isLast = el.dataset.isLast === 'True';

      overviewPanel.classList.add('d-none');
      contentPanel.classList.remove('d-none');

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

      contentPanel.querySelector('#inspector-move-up-btn').style.display = isFirst ? 'none' : 'inline-block';
      contentPanel.querySelector('#inspector-move-down-btn').style.display = isLast ? 'none' : 'inline-block';
      contentPanel.querySelector('#inspector-parent-id').value = itemId;
      contentPanel.querySelector('#inspector-subitem-text').value = '';
      contentPanel.querySelector('#inspector-subitem-llm').value = '';
    }

    treeContainer.addEventListener('click', handleTreeClick);
    if (closeBtn) closeBtn.addEventListener('click', handleClose);

    return function () {
      treeContainer.removeEventListener('click', handleTreeClick);
      if (closeBtn) closeBtn.removeEventListener('click', handleClose);
    };
  }, []);

  return null;
}
