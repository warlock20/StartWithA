/**
 * Company Tagging Module
 * Handles automatic company detection and linking for notes and snippets
 */

// Store current suggestions
let currentSuggestions = null;

/**
 * Detect companies in text and show suggestions modal
 * @param {string} text - The text content to analyze
 * @param {string} targetType - 'note' or 'snippet'
 * @param {number} targetId - The ID of the note or snippet
 * @param {Function} onComplete - Callback function to run after modal closes (e.g., page reload)
 */
async function detectAndSuggestCompanies(text, targetType, targetId, onComplete) {
    try {
        // Call detection API
        const response = await fetch('/sectors/detect-companies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });

        const data = await response.json();

        if (data.success && data.suggestions.total_matches > 0) {
            // Companies found - show modal
            const modal = new bootstrap.Modal(document.getElementById('companySuggestionsModal'));

            // Set context
            document.getElementById('linkTargetType').value = targetType;
            document.getElementById('linkTargetId').value = targetId;

            // Store onComplete callback for later use
            window.companyTaggingOnComplete = onComplete;

            // Show modal with loading state initially
            document.getElementById('companySuggestionsLoading').style.display = 'block';
            document.getElementById('companySuggestionsEmpty').style.display = 'none';
            document.getElementById('companySuggestionsContent').style.display = 'none';

            modal.show();

            // Display suggestions
            currentSuggestions = data.suggestions;
            displayCompanySuggestions(data.suggestions);
        } else {
            // No matches found - skip modal and just run completion callback
            console.log('No company mentions detected');
            if (onComplete) {
                onComplete();
            }
        }
    } catch (error) {
        console.error('Error detecting companies:', error);
        showAlert('Error detecting companies.', 'error');
        // Still run completion callback even on error
        if (onComplete) {
            onComplete();
        }
    }
}

/**
 * Display company suggestions in the modal
 * @param {Object} suggestions - The suggestions object from the API
 */
function displayCompanySuggestions(suggestions) {
    document.getElementById('companySuggestionsLoading').style.display = 'none';
    document.getElementById('companySuggestionsContent').style.display = 'block';

    const highConfDiv = document.getElementById('highConfidenceSuggestions');
    const mediumConfDiv = document.getElementById('mediumConfidenceSuggestions');
    const highList = document.getElementById('highConfidenceList');
    const mediumList = document.getElementById('mediumConfidenceList');

    // Clear previous content
    highList.innerHTML = '';
    mediumList.innerHTML = '';

    // Display high confidence suggestions
    if (suggestions.high_confidence && suggestions.high_confidence.length > 0) {
        highConfDiv.style.display = 'block';
        suggestions.high_confidence.forEach(company => {
            highList.appendChild(createCompanySuggestionItem(company, true));
        });
    } else {
        highConfDiv.style.display = 'none';
    }

    // Display medium confidence suggestions
    if (suggestions.medium_confidence && suggestions.medium_confidence.length > 0) {
        mediumConfDiv.style.display = 'block';
        suggestions.medium_confidence.forEach(company => {
            mediumList.appendChild(createCompanySuggestionItem(company, false));
        });
    } else {
        mediumConfDiv.style.display = 'none';
    }
}

/**
 * Create a company suggestion checkbox item
 * @param {Object} company - Company data
 * @param {boolean} autoSelect - Whether to auto-select high confidence matches
 * @returns {HTMLElement}
 */
function createCompanySuggestionItem(company, autoSelect) {
    const div = document.createElement('div');
    div.className = 'company-suggestion-item' + (autoSelect ? ' selected' : '');

    div.innerHTML = `
        <div class="form-check">
            <input class="form-check-input"
                   type="checkbox"
                   value="${company.id}"
                   id="companySuggestion${company.id}"
                   ${autoSelect ? 'checked' : ''}>
            <label class="form-check-label" for="companySuggestion${company.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="fw-bold">${company.name}</div>
                        <div class="mt-1">
                            <span class="company-ticker">${company.ticker}</span>
                            ${company.sector ? `<span class="company-sector-badge ms-1">${company.sector}</span>` : ''}
                        </div>
                        <div class="mt-1">
                            <small class="text-muted">
                                Matched: "<em>${company.matched_text}</em>"
                            </small>
                        </div>
                    </div>
                </div>
            </label>
        </div>
    `;

    // Toggle selection on click
    div.addEventListener('click', function(e) {
        if (e.target.tagName !== 'INPUT') {
            const checkbox = div.querySelector('input[type="checkbox"]');
            checkbox.checked = !checkbox.checked;
            div.classList.toggle('selected', checkbox.checked);
        } else {
            div.classList.toggle('selected', e.target.checked);
        }
    });

    return div;
}

/**
 * Link selected companies to the note or snippet
 */
async function linkSelectedCompanies() {
    const targetType = document.getElementById('linkTargetType').value;
    const targetId = document.getElementById('linkTargetId').value;

    // Get selected company IDs
    const checkboxes = document.querySelectorAll('#companySuggestionsContent input[type="checkbox"]:checked');
    const companyIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    if (companyIds.length === 0) {
        showAlert('Please select at least one company to link.', 'warning');
        return;
    }

    // Disable button during request
    const btn = document.getElementById('linkSelectedCompaniesBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Linking...';

    try {
        const endpoint = targetType === 'note'
            ? `/sectors/note/${targetId}/link-companies`
            : `/sectors/snippet/${targetId}/link-companies`;

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ company_ids: companyIds })
        });

        const data = await response.json();

        if (data.success) {
            showAlert(`Successfully linked ${companyIds.length} ${companyIds.length === 1 ? 'company' : 'companies'}`, 'success');

            // Update UI to show linked companies
            updateLinkedCompaniesDisplay(targetType, targetId, data.linked_companies);

            // Close modal
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('companySuggestionsModal'));
            modalInstance.hide();

            // Run completion callback after modal closes
            if (window.companyTaggingOnComplete) {
                setTimeout(() => {
                    window.companyTaggingOnComplete();
                    window.companyTaggingOnComplete = null;
                }, 300); // Small delay to let modal close animation finish
            }
        } else {
            showAlert(data.error || 'Failed to link companies', 'error');
        }
    } catch (error) {
        console.error('Error linking companies:', error);
        showAlert('Error linking companies. Please try again.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

/**
 * Skip company linking and close modal
 */
function skipCompanyLinking() {
    // Close modal
    const modalInstance = bootstrap.Modal.getInstance(document.getElementById('companySuggestionsModal'));
    if (modalInstance) {
        modalInstance.hide();
    }

    // Run completion callback
    if (window.companyTaggingOnComplete) {
        setTimeout(() => {
            window.companyTaggingOnComplete();
            window.companyTaggingOnComplete = null;
        }, 300);
    }
}

/**
 * Update the UI to display linked companies on a note/snippet card
 * @param {string} targetType - 'note' or 'snippet'
 * @param {number} targetId - The ID of the note or snippet
 * @param {Array} companies - Array of linked company objects
 */
function updateLinkedCompaniesDisplay(targetType, targetId, companies) {
    const cardSelector = targetType === 'note'
        ? `[data-note-id="${targetId}"]`
        : `[data-snippet-id="${targetId}"]`;

    const card = document.querySelector(cardSelector);
    if (!card) return;

    // Find or create companies container
    let companiesContainer = card.querySelector('.linked-companies-container');
    if (!companiesContainer) {
        companiesContainer = document.createElement('div');
        companiesContainer.className = 'linked-companies-container mt-2';

        // Insert before footer or at end of card body
        const cardBody = card.querySelector('.card-body');
        const cardFooter = card.querySelector('.card-footer');
        if (cardFooter) {
            cardBody.insertBefore(companiesContainer, cardFooter);
        } else {
            cardBody.appendChild(companiesContainer);
        }
    }

    // Clear and populate
    companiesContainer.innerHTML = '';
    if (companies.length > 0) {
        const companiesHTML = companies.map(company => `
            <span class="company-tag" data-company-id="${company.id}">
                <i class="bi bi-building"></i>
                <span class="company-tag-name">${company.name}</span>
                <span class="company-tag-ticker">${company.ticker}</span>
                <button class="company-tag-remove" onclick="unlinkCompany('${targetType}', ${targetId}, ${company.id})" title="Remove link">
                    <i class="bi bi-x"></i>
                </button>
            </span>
        `).join('');

        companiesContainer.innerHTML = `
            <div class="small text-muted mb-1">
                <i class="bi bi-link-45deg"></i> Linked Companies:
            </div>
            <div class="company-tags-list">${companiesHTML}</div>
        `;
    }
}

/**
 * Unlink a company from a note or snippet
 * @param {string} targetType - 'note' or 'snippet'
 * @param {number} targetId - The ID of the note or snippet
 * @param {number} companyId - The ID of the company to unlink
 */
async function unlinkCompany(targetType, targetId, companyId) {
    if (!confirm('Remove this company link?')) return;

    try {
        const endpoint = targetType === 'note'
            ? `/sectors/note/${targetId}/unlink-company/${companyId}`
            : `/sectors/snippet/${targetId}/unlink-company/${companyId}`;

        showToast('Removing…', 'loading');
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            // Remove the tag from UI
            const tag = document.querySelector(`[data-company-id="${companyId}"]`);
            if (tag) {
                tag.remove();

                // Check if there are any remaining tags
                const cardSelector = targetType === 'note'
                    ? `[data-note-id="${targetId}"]`
                    : `[data-snippet-id="${targetId}"]`;
                const card = document.querySelector(cardSelector);
                const tagsList = card?.querySelector('.company-tags-list');

                if (tagsList && tagsList.children.length === 0) {
                    // Remove entire container if no more companies
                    const container = card.querySelector('.linked-companies-container');
                    if (container) container.remove();
                }
            }

            showToast('Removed', 'success');
            showAlert('Company unlinked', 'success');
        } else {
            showToast(data.error || 'Failed to unlink company', 'danger');
            showAlert(data.error || 'Failed to unlink company', 'error');
        }
    } catch (error) {
        showToast('Failed to unlink company', 'danger');
        console.error('Error unlinking company:', error);
        showAlert('Error unlinking company', 'error');
    }
}

/**
 * Show an alert message
 * @param {string} message - The message to display
 * @param {string} type - 'success', 'error', 'warning', 'info'
 */
function showAlert(message, type = 'info') {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.style.position = 'fixed';
    alertDiv.style.top = '20px';
    alertDiv.style.right = '20px';
    alertDiv.style.zIndex = '9999';
    alertDiv.style.minWidth = '300px';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 4000);
}
