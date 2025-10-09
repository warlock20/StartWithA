/**
 * Sector Research Snippets - Save and manage research snippets
 * Handles snippet saving, filtering, and categorization
 */

// ==================== SNIPPET SAVING ====================

function openSaveSnippetModal() {
    // selectedSnippetText is set by sector-document.js
    if (!selectedSnippetText || selectedSnippetText.trim().length === 0) {
        alert('Please select some text first');
        return;
    }

    // Show preview
    document.getElementById('snippetPreview').textContent = selectedSnippetText;

    // Open modal
    const modal = new bootstrap.Modal(document.getElementById('saveSnippetModal'));
    modal.show();
}

function saveSnippet() {
    const category = document.getElementById('snippetCategory').value;
    const tags = document.getElementById('snippetTags').value;
    const notes = document.getElementById('snippetNotes').value;

    if (!category) {
        alert('Please select a category');
        return;
    }

    if (!selectedSnippetText || selectedSnippetText.trim().length === 0) {
        alert('No text selected');
        return;
    }

    // Save via API
    fetch(window.sectorUrls.addSnippet, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            content: selectedSnippetText,
            category: category,
            tags: tags,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('saveSnippetModal'));
            modal.hide();

            // Clear form
            document.getElementById('snippetCategory').value = '';
            document.getElementById('snippetTags').value = '';
            document.getElementById('snippetNotes').value = '';
            selectedSnippetText = '';

            // Reload page to show new snippet
            location.reload();
        } else {
            alert('Error saving snippet: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error saving snippet');
        console.error(err);
    });
}

// ==================== SNIPPET FILTERING ====================

function filterSnippets(category) {
    // Update active button
    document.querySelectorAll('.snippet-category-filter button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.category === category) {
            btn.classList.add('active');
        }
    });

    // Filter snippet cards
    const snippets = document.querySelectorAll('.snippet-card');
    snippets.forEach(snippet => {
        if (category === 'all' || snippet.dataset.category === category) {
            snippet.style.display = 'block';
        } else {
            snippet.style.display = 'none';
        }
    });
}
