document.addEventListener('DOMContentLoaded', function () {
    const treeContainer = document.querySelector('.checklist-tree');
    const inspectorPanel = document.getElementById('inspector-panel');
    const overviewPanel = document.getElementById('inspector-overview');
    const contentPanel = document.getElementById('inspector-content');
    const closeBtn = document.getElementById('inspector-close-btn');

    if (!treeContainer || !inspectorPanel || !overviewPanel || !contentPanel) {
        return;
    }

    const editUrlTemplate = inspectorPanel.dataset.editUrlTemplate;
    const deleteUrlTemplate = inspectorPanel.dataset.deleteUrlTemplate;
    const moveUrlTemplate = inspectorPanel.dataset.moveUrlTemplate;

    treeContainer.addEventListener('click', function(event) {
        const clickedItemLink = event.target.closest('.checklist-tree-item a');
        if (clickedItemLink) {
            event.preventDefault();
            const currentActive = treeContainer.querySelector('a.active');
            if (currentActive) {
                currentActive.classList.remove('active');
            }
            clickedItemLink.classList.add('active');
            populateInspector(clickedItemLink);
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            contentPanel.classList.add('d-none');
            overviewPanel.classList.remove('d-none');
            const currentActive = treeContainer.querySelector('a.active');
            if (currentActive) {
                currentActive.classList.remove('active');
            }
        });
    }

    function populateInspector(itemElement) {
        const itemId = itemElement.dataset.itemId;
        const itemText = itemElement.dataset.itemText;
        const llmPrompt = itemElement.dataset.llmPrompt;
        const isFirst = itemElement.dataset.isFirst === 'True';
        const isLast = itemElement.dataset.isLast === 'True';

        overviewPanel.classList.add('d-none');
        contentPanel.classList.remove('d-none');

        contentPanel.querySelector('#inspector-item-text').textContent = itemText;
        const llmPromptDisplay = contentPanel.querySelector('#inspector-llm-prompt-display');
        const llmPromptText = contentPanel.querySelector('#inspector-llm-prompt');
        if (llmPrompt) {
            llmPromptText.textContent = llmPrompt;
            llmPromptDisplay.style.display = 'block';
        } else {
            llmPromptDisplay.style.display = 'none';
        }

        if (editUrlTemplate) {
            contentPanel.querySelector('#inspector-edit-btn').href = editUrlTemplate.replace('/0', `/${itemId}`);
        }
        if (deleteUrlTemplate) {
            contentPanel.querySelector('#inspector-delete-form').action = deleteUrlTemplate.replace('/0', `/${itemId}`);
        }
        if (moveUrlTemplate) {
            const moveUpUrl = moveUrlTemplate.replace('/0/', `/${itemId}/`).replace('__DIRECTION__', 'up');
            const moveDownUrl = moveUrlTemplate.replace('/0/', `/${itemId}/`).replace('__DIRECTION__', 'down');
            contentPanel.querySelector('#inspector-move-up-form').action = moveUpUrl;
            contentPanel.querySelector('#inspector-move-down-form').action = moveDownUrl;
        }

        const moveUpBtn = contentPanel.querySelector('#inspector-move-up-btn');
        const moveDownBtn = contentPanel.querySelector('#inspector-move-down-btn');
        moveUpBtn.style.display = isFirst ? 'none' : 'inline-block';
        moveDownBtn.style.display = isLast ? 'none' : 'inline-block';

        contentPanel.querySelector('#inspector-parent-id').value = itemId;
        contentPanel.querySelector('#inspector-subitem-text').value = '';
        contentPanel.querySelector('#inspector-subitem-llm').value = '';
    }
});