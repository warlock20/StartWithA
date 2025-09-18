// app/static/js/checklist_form.js

let itemIdCounter = 1;

// This function creates the HTML for a new item form group with support for multiple nesting levels
function createNewItem(itemCount, level = 0, parentPath = '') {
    const newItemDiv = document.createElement('div');
    const uniqueId = `item_${itemIdCounter++}`;
    const isSubItem = level > 0;
    const indentLevel = level * 1.5; // 1.5rem per level
    const currentPath = parentPath ? `${parentPath}.${itemCount}` : itemCount.toString();

    // Different colors for different levels
    const levelColors = ['success', 'primary', 'info', 'warning', 'secondary'];
    const borderColor = levelColors[Math.min(level, levelColors.length - 1)];

    newItemDiv.className = `card border-${borderColor} p-3 mb-2 initial-item-group ${isSubItem ? 'sub-item' : 'main-item'} level-${level}`;
    newItemDiv.style.marginLeft = `${indentLevel}rem`;
    newItemDiv.setAttribute('data-item-id', uniqueId);
    newItemDiv.setAttribute('data-level', level);
    newItemDiv.setAttribute('data-path', currentPath);
    newItemDiv.setAttribute('data-parent-path', parentPath);

    // Create tree-like visual indicator
    const treeIndicator = level > 0 ? '│'.repeat(level - 1) + (level > 0 ? '├─ ' : '') : '';
    const levelLabel = level === 0 ? `Item ${itemCount}` : `${treeIndicator}Sub-item ${itemCount}`;

    // Using template literals (backticks) for easy multiline HTML
    newItemDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
            <div class="d-flex align-items-center gap-2">
                <label class="form-label fw-bold mb-0" style="color: var(--bs-${borderColor}); font-size: ${isSubItem ? '0.9rem' : '1rem'}">
                    <span class="tree-indicator">${levelLabel}</span>
                    <span class="badge bg-${borderColor} ms-2" style="font-size: 0.7rem">${uniqueId}</span>
                </label>
                <div class="level-badge">
                    <span class="badge bg-light text-dark">L${level}</span>
                </div>
            </div>
            <div class="d-flex gap-1">
                <button type="button" class="btn btn-outline-${borderColor} btn-sm" onclick="addSubItem('${uniqueId}', ${level + 1})" title="Add Sub-item">
                    <i class="bi bi-plus"></i> ${level < 3 ? 'Sub-item' : '+'}
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveItem('${uniqueId}', 'up')" title="Move Up">
                    <i class="bi bi-arrow-up"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveItem('${uniqueId}', 'down')" title="Move Down">
                    <i class="bi bi-arrow-down"></i>
                </button>
                <button type="button" class="btn-close" aria-label="Close" onclick="removeItem('${uniqueId}')"></button>
            </div>
        </div>
        <div class="row mt-2">
            <div class="col-md-${level === 0 ? '12' : '12'}">
                <div class="mb-2">
                    <label class="form-label small">Item Text:</label>
                    <input type="text" class="form-control ${isSubItem ? 'form-control-sm' : ''}"
                           name="item_text[]" placeholder="Enter ${level === 0 ? 'main' : 'sub-'}item text" required>
                </div>
            </div>
        </div>
        <div class="mb-2">
            <label class="form-label small">Optional LLM Prompt:</label>
            <textarea class="form-control form-control-sm" name="item_llm_prompt[]" rows="2"
                      placeholder="E.g., What are the key revenue drivers?"></textarea>
        </div>
        <input type="hidden" name="item_level[]" value="${level}">
        <input type="hidden" name="item_path[]" value="${currentPath}">
        <input type="hidden" name="parent_path[]" value="${parentPath}">
        <input type="hidden" name="item_priority[]" value="normal">
        <div class="sub-items-container mt-2"></div>
    `;
    return newItemDiv;
}

// Function to add a sub-item to a specific parent item
function addSubItem(parentId, newLevel = 1) {
    const parentElement = document.querySelector(`[data-item-id="${parentId}"]`);
    if (!parentElement) return;

    // Prevent too deep nesting (limit to 5 levels)
    if (newLevel > 4) {
        showTemporaryMessage('Maximum nesting level reached (5 levels)', 'warning');
        return;
    }

    const subItemsContainer = parentElement.querySelector('.sub-items-container');
    const parentPath = parentElement.getAttribute('data-path');

    // Count existing direct children to determine the next number
    const existingChildren = Array.from(subItemsContainer.children).filter(child =>
        child.getAttribute('data-parent-path') === parentPath
    );
    const subItemNumber = existingChildren.length + 1;

    const subItem = createNewItem(subItemNumber, newLevel, parentPath);
    subItemsContainer.appendChild(subItem);

    // Focus on the new sub-item text input
    const textInput = subItem.querySelector('input[name="item_text[]"]');
    if (textInput) {
        textInput.focus();
    }

    // Scroll to the new sub-item
    subItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Update the visual tree after adding
    updateItemNumbers();

    // Update progress stats if function exists
    if (typeof updateProgressStats === 'function') {
        updateProgressStats();
    }
}

// Function to remove an item and all its sub-items
function removeItem(itemId) {
    const itemElement = document.querySelector(`[data-item-id="${itemId}"]`);
    if (!itemElement) return;

    const level = parseInt(itemElement.getAttribute('data-level'));
    const allSubItems = itemElement.querySelectorAll('.initial-item-group');

    if (allSubItems.length > 0) {
        if (!confirm(`This will remove this item and all ${allSubItems.length} nested sub-items. Are you sure?`)) {
            return;
        }
    }

    // Remove the item and all its descendants
    itemElement.remove();

    // Update numbering for all items
    updateItemNumbers();

    // Update progress stats if function exists
    if (typeof updateProgressStats === 'function') {
        updateProgressStats();
    }
}

// Function to move items up or down
function moveItem(itemId, direction) {
    const itemElement = document.querySelector(`[data-item-id="${itemId}"]`);
    if (!itemElement) return;

    const parentPath = itemElement.getAttribute('data-parent-path');
    const container = itemElement.parentElement;

    // Get all siblings at the same level
    const siblings = Array.from(container.children).filter(child =>
        child.getAttribute('data-parent-path') === parentPath &&
        child.classList.contains('initial-item-group')
    );

    const currentIndex = siblings.indexOf(itemElement);

    if (direction === 'up' && currentIndex > 0) {
        container.insertBefore(itemElement, siblings[currentIndex - 1]);
    } else if (direction === 'down' && currentIndex < siblings.length - 1) {
        container.insertBefore(siblings[currentIndex + 1], itemElement);
    } else {
        showTemporaryMessage(`Cannot move ${direction}. Item is already at the ${direction === 'up' ? 'top' : 'bottom'}.`, 'info');
        return;
    }

    updateItemNumbers();
    itemElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Function to update item numbers and paths
function updateItemNumbers() {
    const container = document.getElementById('initial-items-container');
    updateNumbersRecursively(container, '', 0);
}

function updateNumbersRecursively(container, parentPath, level) {
    const directChildren = Array.from(container.children).filter(child =>
        child.getAttribute('data-parent-path') === parentPath &&
        child.classList.contains('initial-item-group')
    );

    directChildren.forEach((item, index) => {
        const itemNumber = index + 1;
        const currentPath = parentPath ? `${parentPath}.${itemNumber}` : itemNumber.toString();

        item.setAttribute('data-path', currentPath);

        // Update the label
        const label = item.querySelector('.tree-indicator');
        if (label) {
            const treeIndicator = level > 0 ? '│'.repeat(level - 1) + '├─ ' : '';
            const levelLabel = level === 0 ? `Item ${itemNumber}` : `${treeIndicator}Sub-item ${itemNumber}`;
            label.textContent = levelLabel;
        }

        // Update hidden path fields
        const pathInput = item.querySelector('input[name="item_path[]"]');
        if (pathInput) {
            pathInput.value = currentPath;
        }

        // Recursively update children
        const subItemsContainer = item.querySelector('.sub-items-container');
        if (subItemsContainer) {
            updateNumbersRecursively(subItemsContainer, currentPath, level + 1);
        }
    });
}

// Helper function for temporary messages (defined here for addSubItem)
function showTemporaryMessage(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 3000);
}

// This runs after the entire page is loaded
document.addEventListener('DOMContentLoaded', function() {
    const addItemBtn = document.getElementById('add-item-btn');
    const container = document.getElementById('initial-items-container');

    if (addItemBtn && container) {
        // Function to add a new main item to the container
        const addNewMainItem = () => {
            const mainItemsCount = container.querySelectorAll('.main-item').length + 1;
            const newItemElement = createNewItem(mainItemsCount, 0, '');
            container.appendChild(newItemElement);
            updateItemNumbers();

            // Update progress stats if function exists
            if (typeof updateProgressStats === 'function') {
                updateProgressStats();
            }

            // Focus on the new item's text input
            const textInput = newItemElement.querySelector('input[name="item_text[]"]');
            if (textInput) {
                textInput.focus();
            }
        };

        // Add the first item automatically when the page loads
        addNewMainItem();

        // Add another item when the button is clicked
        addItemBtn.addEventListener('click', function(e) {
            e.preventDefault();
            addNewMainItem();
        });
    }

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Enter to add new main item
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('add-item-btn')?.click();
        }
    });
});

