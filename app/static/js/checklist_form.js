// app/static/js/checklist_form.js

// Wait for the document to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    const addItemBtn = document.getElementById('add-item-btn');
    const container = document.getElementById('initial-items-container');

    if (addItemBtn && container) { // Check that both elements exist
        addItemBtn.addEventListener('click', function() {
            // Count how many item groups we already have to number the new one correctly
            const itemCount = container.getElementsByClassName('initial-item-group').length + 1;

            // Create a new div element for the new item group
            const newItemDiv = document.createElement('div');
            newItemDiv.className = 'card bg-light p-3 mb-3 initial-item-group';

            // Set the inner HTML for the new input fields
            // Using template literals (backticks) for easy multiline HTML
            newItemDiv.innerHTML = `
                <div class="mb-2">
                    <label class="form-label">Item ${itemCount} Text:</label>
                    <input type="text" class="form-control" name="item_text[]" placeholder="Item ${itemCount} text">
                </div>
                <div>
                    <label class="form-label">Optional LLM Prompt for Item ${itemCount}:</label>
                    <textarea class="form-control" name="item_llm_prompt[]" rows="2" placeholder="E.g., What are the key revenue drivers?"></textarea>
                </div>
            `;

            // Append the new div to the container
            container.appendChild(newItemDiv);
        });
    }
});