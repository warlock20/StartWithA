// app/static/js/checklist_form.js
// This function creates the HTML for a new item form group
function createNewItem(itemCount) {
    const newItemDiv = document.createElement('div');
    newItemDiv.className = 'card bg-light p-3 mb-3 initial-item-group';

    // Using template literals (backticks) for easy multiline HTML
    newItemDiv.innerHTML = `
        <div class="d-flex justify-content-between">
            <label class="form-label fw-bold">Item ${itemCount}</label>
            <button type="button" class="btn-close" aria-label="Close" onclick="this.closest('.initial-item-group').remove()"></button>
        </div>
        <div class="mb-2">
            <label class="form-label small">Item Text:</label>
            <input type="text" class="form-control" name="item_text[]" placeholder="Enter item text">
        </div>
        <div>
            <label class="form-label small">Optional LLM Prompt:</label>
            <textarea class="form-control" name="item_llm_prompt[]" rows="2" placeholder="E.g., What are the key revenue drivers?"></textarea>
        </div>
    `;
    return newItemDiv;
}

// This runs after the entire page is loaded
document.addEventListener('DOMContentLoaded', function() {
    const addItemBtn = document.getElementById('add-item-btn');
    const container = document.getElementById('initial-items-container');

    if (addItemBtn && container) {
        // Function to add a new item to the container
        const addNewItem = () => {
            const itemCount = container.getElementsByClassName('initial-item-group').length + 1;
            const newItemElement = createNewItem(itemCount);
            container.appendChild(newItemElement);
        };

        // Add the first item automatically when the page loads
        addNewItem();

        // Add another item when the button is clicked
        addItemBtn.addEventListener('click', addNewItem);
    }
});

