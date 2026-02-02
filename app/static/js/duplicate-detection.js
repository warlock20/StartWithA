/**
 * Real-time duplicate detection for companies and ideas
 */

class DuplicateDetector {
    constructor(options = {}) {
        this.nameInput = options.nameInput;
        this.tickerInput = options.tickerInput;
        this.alertContainer = options.alertContainer;
        this.submitButton = options.submitButton;
        this.entityType = options.entityType || 'company'; // 'company' or 'idea'
        this.debounceTime = options.debounceTime || 500;

        this.debounceTimer = null;
        this.lastCheck = { name: '', ticker: '' };

        this.init();
    }

    init() {
        if (this.nameInput) {
            this.nameInput.addEventListener('input', () => this.debouncedCheck());
        }
        if (this.tickerInput) {
            this.tickerInput.addEventListener('input', () => this.debouncedCheck());
        }
    }

    debouncedCheck() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.checkDuplicates(), this.debounceTime);
    }

    async checkDuplicates() {
        const name = this.nameInput?.value?.trim() || '';
        const ticker = this.tickerInput?.value?.trim() || '';

        // Skip if values haven't changed
        if (name === this.lastCheck.name && ticker === this.lastCheck.ticker) {
            return;
        }

        // Skip if both are empty
        if (!name && !ticker) {
            this.clearAlerts();
            return;
        }

        this.lastCheck = { name, ticker };

        try {
            const response = await fetch('/api/check-duplicates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    ticker_symbol: ticker,
                    entity_type: this.entityType
                })
            });

            if (response.ok) {
                const result = await response.json();
                this.displayResults(result);
            }
        } catch (error) {
            console.error('Duplicate check failed:', error);
        }
    }

    displayResults(result) {
        this.clearAlerts();

        if (!result.is_duplicate && !result.suggestions.length && !result.similar_matches.length) {
            this.showSuccess('✅ No duplicates found');
            this.enableSubmit();
            return;
        }

        if (result.is_duplicate) {
            this.disableSubmit();
        } else {
            this.enableSubmit();
        }

        // Show exact matches (blocking)
        result.exact_matches.forEach(match => {
            this.showAlert('danger', match.message, match);
        });

        // Show similar matches (warnings)
        result.similar_matches.forEach(match => {
            const similarity = Math.round(match.similarity * 100);
            this.showAlert('warning', `${match.message} (${similarity}% similar)`, match);
        });

        // Show suggestions (info)
        result.suggestions.forEach(suggestion => {
            this.showAlert('info', suggestion.message, suggestion);
        });
    }

    showAlert(type, message, data = {}) {
        if (!this.alertContainer) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;

        let actionButtons = '';
        if (data.type === 'ticker_conflict' && data.company) {
            actionButtons = `
                <div class="mt-2">
                    <a href="/companies/${data.company.id}/edit" class="btn btn-sm btn-outline-primary">
                        Update Existing Company
                    </a>
                </div>
            `;
        } else if (data.type === 'exact_duplicate' && data.company) {
            actionButtons = `
                <div class="mt-2">
                    <a href="/companies/${data.company.id}" class="btn btn-sm btn-outline-primary">
                        View Existing Company
                    </a>
                </div>
            `;
        } else if (data.type === 'killed_idea_exists' && data.idea) {
            actionButtons = `
                <div class="mt-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary"
                            onclick="resurrectIdea(${data.idea.id})">
                        Resurrect Previous Idea
                    </button>
                    <small class="text-muted d-block mt-1">
                        Previously killed: ${data.idea.kill_reason || 'No reason provided'}
                    </small>
                </div>
            `;
        } else if (data.type === 'promote_existing_company' && data.company) {
            actionButtons = `
                <div class="mt-2">
                    <a href="/research/workflow/intelligent-routing?company_id=${data.company.id}&source=duplicate_detection"
                       class="btn btn-sm btn-outline-success">
                        <i class="bi bi-rocket-takeoff"></i> Start Research
                    </a>
                    <a href="/companies/${data.company.id}" class="btn btn-sm btn-outline-secondary ms-2">
                        <i class="bi bi-building"></i> View Company
                    </a>
                </div>
            `;
        }

        alertDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="flex-grow-1">
                    <strong>${this.getAlertIcon(type)}</strong> ${message}
                    ${actionButtons}
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        this.alertContainer.appendChild(alertDiv);
    }

    showSuccess(message) {
        if (!this.alertContainer) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success fade show';
        alertDiv.innerHTML = `
            <small>${message}</small>
        `;

        this.alertContainer.appendChild(alertDiv);

        // Auto-hide success messages after 3 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 3000);
    }

    getAlertIcon(type) {
        const icons = {
            'danger': '🚫',
            'warning': '⚠️',
            'info': 'ℹ️',
            'success': '✅'
        };
        return icons[type] || '';
    }

    clearAlerts() {
        if (this.alertContainer) {
            this.alertContainer.innerHTML = '';
        }
    }

    disableSubmit() {
        if (this.submitButton) {
            this.submitButton.disabled = true;
            this.submitButton.classList.add('btn-secondary');
            this.submitButton.classList.remove('btn-primary');
        }
    }

    enableSubmit() {
        if (this.submitButton) {
            this.submitButton.disabled = false;
            this.submitButton.classList.remove('btn-secondary');
            this.submitButton.classList.add('btn-primary');
        }
    }
}

// Helper function for resurrecting killed ideas
function resurrectIdea(ideaId) {
    if (confirm('Are you sure you want to resurrect this previously killed idea?')) {
        fetch(`/ideas/${ideaId}/resurrect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = `/ideas/${ideaId}`;
            } else {
                alert('Failed to resurrect idea: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to resurrect idea');
        });
    }
}

// Auto-initialize for common forms
document.addEventListener('DOMContentLoaded', function() {
    // Company forms
    const companyNameInput = document.getElementById('company-name');
    const companyTickerInput = document.getElementById('company-ticker');
    const companyAlertContainer = document.getElementById('duplicate-alerts');
    const companySubmitButton = document.querySelector('form[data-entity="company"] button[type="submit"]');

    if (companyNameInput || companyTickerInput) {
        new DuplicateDetector({
            nameInput: companyNameInput,
            tickerInput: companyTickerInput,
            alertContainer: companyAlertContainer,
            submitButton: companySubmitButton,
            entityType: 'company'
        });
    }

    // Idea forms
    const ideaNameInput = document.getElementById('idea-name');
    const ideaTickerInput = document.getElementById('idea-ticker');
    const ideaAlertContainer = document.getElementById('duplicate-alerts');
    const ideaSubmitButton = document.querySelector('form[data-entity="idea"] button[type="submit"]');

    if (ideaNameInput || ideaTickerInput) {
        new DuplicateDetector({
            nameInput: ideaNameInput,
            tickerInput: ideaTickerInput,
            alertContainer: ideaAlertContainer,
            submitButton: ideaSubmitButton,
            entityType: 'idea'
        });
    }
});