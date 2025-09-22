/**
 * Reusable Company Search & Selection Component
 * Extracted from Journal Entry functionality for use across the platform
 */

class CompanySearchComponent {
    constructor(config = {}) {
        this.config = {
            modalId: config.modalId || 'companySearchModal',
            searchInputId: config.searchInputId || 'companySearch',
            resultsId: config.resultsId || 'searchResults',
            resultsListId: config.resultsListId || 'resultsList',
            quickAddFormId: config.quickAddFormId || 'quickAddForm',
            selectedDisplayId: config.selectedDisplayId || 'selectedCompanyDisplay',
            confirmBtnId: config.confirmBtnId || 'confirmCompanySelection',
            // Target form fields for integration
            hiddenFieldId: config.hiddenFieldId || 'company_id',
            displayInfoId: config.displayInfoId || 'companyDisplayInfo',
            selectedInfoId: config.selectedInfoId || 'selectedCompanyInfo',
            clearBtnId: config.clearBtnId || 'clearCompanyBtn',
            // API endpoints
            searchEndpoint: config.searchEndpoint || '/companies/api/companies/search',
            createEndpoint: config.createEndpoint || '/companies/api/companies/create',
            ...config
        };

        this.selectedCompany = null;
        this.callback = null;
        this.searchDebounceTimer = null;
        this.modal = null;
    }

    /**
     * Initialize the component - call this after DOM is ready
     */
    init() {
        this.modal = document.getElementById(this.config.modalId);
        if (!this.modal) {
            console.warn(`Company search modal ${this.config.modalId} not found`);
            return;
        }

        this.setupEventListeners();
        console.log('Company search component initialized');
    }

    /**
     * Open the company search modal
     * @param {Function} callback - Function to call when company is selected
     */
    open(callback) {
        console.log('Opening company modal with callback:', !!callback);
        this.callback = callback;
        this.selectedCompany = null;

        // Show modal
        const modalInstance = new bootstrap.Modal(this.modal);
        modalInstance.show();

        // Reset modal state after showing
        setTimeout(() => {
            this.resetModal();
        }, 100);
    }

    /**
     * Close the modal
     */
    close() {
        const modalInstance = bootstrap.Modal.getInstance(this.modal);
        if (modalInstance) {
            modalInstance.hide();
        }
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Search input
        const searchInput = document.getElementById(this.config.searchInputId);
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchDebounceTimer);
                this.searchDebounceTimer = setTimeout(() => {
                    this.performSearch(e.target.value.trim());
                }, 300);
            });
        }

        // Confirm button
        const confirmBtn = document.getElementById(this.config.confirmBtnId);
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => {
                this.confirmSelection();
            });
        }

        // Add new company button
        const addBtn = document.getElementById('addNewCompanyBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.addNewCompany();
            });
        }

        // Clear company button (external to modal)
        const clearBtn = document.getElementById(this.config.clearBtnId);
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearSelection();
            });
        }

        // Auto-uppercase ticker field
        const tickerField = document.getElementById('newCompanyTicker');
        if (tickerField) {
            tickerField.addEventListener('input', (e) => {
                e.target.value = e.target.value.toUpperCase();
            });
        }
    }

    /**
     * Reset modal to initial state
     */
    resetModal() {
        // Clear search
        const searchInput = document.getElementById(this.config.searchInputId);
        if (searchInput) searchInput.value = '';

        // Hide all sections
        this.hideElement(this.config.resultsId);
        this.hideElement(this.config.quickAddFormId);
        this.hideElement(this.config.selectedDisplayId);

        // Disable confirm button
        const confirmBtn = document.getElementById(this.config.confirmBtnId);
        if (confirmBtn) confirmBtn.disabled = true;

        // Clear quick add form
        this.clearQuickAddForm();
    }

    /**
     * Perform company search
     */
    async performSearch(query) {
        if (query.length < 2) {
            this.hideElement(this.config.resultsId);
            this.hideElement(this.config.quickAddFormId);
            return;
        }

        try {
            const response = await fetch(`${this.config.searchEndpoint}?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            this.displaySearchResults(data, query);
        } catch (error) {
            console.error('Search error:', error);
            this.hideElement(this.config.resultsId);
        }
    }

    /**
     * Display search results
     */
    displaySearchResults(data, query) {
        const resultsList = document.getElementById(this.config.resultsListId);
        if (!resultsList) return;

        resultsList.innerHTML = '';

        // Yahoo Finance suggestions
        if (data.yahoo_suggestions && data.yahoo_suggestions.length > 0) {
            data.yahoo_suggestions.forEach(suggestion => {
                const item = this.createYahooResultItem(suggestion);
                resultsList.appendChild(item);
            });
        }

        // User's existing companies
        if (data.user_companies && data.user_companies.length > 0) {
            data.user_companies.forEach(company => {
                const item = this.createUserCompanyItem(company);
                resultsList.appendChild(item);
            });
        }

        // Show results or quick add form
        if (resultsList.children.length > 0) {
            this.showElement(this.config.resultsId);
            this.hideElement(this.config.quickAddFormId);
        } else {
            this.hideElement(this.config.resultsId);
            this.showQuickAddForm(query);
        }
    }

    /**
     * Create Yahoo Finance result item
     */
    createYahooResultItem(suggestion) {
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item list-group-item-action';
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h6 class="mb-1">${suggestion.name}</h6>
                    <p class="mb-1">${suggestion.ticker_symbol}</p>
                    <small class="text-muted">${suggestion.industry || 'Industry not specified'}</small>
                </div>
                <div class="text-end">
                    <small class="text-success">🆕 Add to Portfolio</small>
                </div>
            </div>
        `;

        item.addEventListener('click', (e) => {
            e.preventDefault();
            this.selectYahooCompany(suggestion);
        });

        return item;
    }

    /**
     * Create user company item
     */
    createUserCompanyItem(company) {
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item list-group-item-action';
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h6 class="mb-1">${company.name}</h6>
                    <p class="mb-1">${company.ticker_symbol || 'No ticker'}</p>
                    <small class="text-muted">${company.industry || 'Industry not specified'}</small>
                </div>
                <div class="text-end">
                    <small class="text-primary">📁 Your Portfolio</small>
                </div>
            </div>
        `;

        item.addEventListener('click', (e) => {
            e.preventDefault();
            this.selectCompany(company);
        });

        return item;
    }

    /**
     * Show quick add form
     */
    showQuickAddForm(query) {
        // Pre-fill based on search query
        if (query.length <= 5 && query.match(/^[A-Z]+$/)) {
            const tickerField = document.getElementById('newCompanyTicker');
            if (tickerField) tickerField.value = query.toUpperCase();
        } else {
            const nameField = document.getElementById('newCompanyName');
            if (nameField) nameField.value = query;
        }

        this.showElement(this.config.quickAddFormId);
    }

    /**
     * Select a Yahoo Finance company (creates it first)
     */
    async selectYahooCompany(yahooCompany) {
        const data = {
            ticker_symbol: yahooCompany.ticker_symbol,
            name: yahooCompany.name,
            industry: yahooCompany.industry || null,
            sector: yahooCompany.sector || null
        };

        try {
            const response = await fetch(this.config.createEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                this.selectCompany(result.company);
            } else {
                alert('Error creating company: ' + result.error);
            }
        } catch (error) {
            console.error('Error creating company:', error);
            alert('Error creating company');
        }
    }

    /**
     * Add new company manually
     */
    async addNewCompany() {
        const ticker = document.getElementById('newCompanyTicker').value.trim();
        const name = document.getElementById('newCompanyName').value.trim();
        const industry = document.getElementById('newCompanyIndustry').value.trim();
        const sector = document.getElementById('newCompanySector').value.trim();

        if (!name) {
            alert('Company name is required');
            return;
        }

        const data = {
            ticker_symbol: ticker || null,
            name: name,
            industry: industry || null,
            sector: sector || null
        };

        try {
            const response = await fetch(this.config.createEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                this.selectCompany(result.company);
                this.clearQuickAddForm();
            } else {
                alert('Error creating company: ' + result.error);
            }
        } catch (error) {
            console.error('Error creating company:', error);
            alert('Error creating company');
        }
    }

    /**
     * Select a company
     */
    selectCompany(company) {
        console.log('Selecting company:', company);
        this.selectedCompany = company;

        // Update modal display
        const selectedInfo = document.getElementById('modalSelectedCompanyInfo');
        if (selectedInfo) {
            selectedInfo.innerHTML = `
                <strong>${company.name}</strong><br>
                <small>Ticker: ${company.ticker_symbol || 'N/A'} | Industry: ${company.industry || 'N/A'}</small>
            `;
        }

        this.showElement(this.config.selectedDisplayId);

        // Enable confirm button
        const confirmBtn = document.getElementById(this.config.confirmBtnId);
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }

        // Hide search results and quick add form
        this.hideElement(this.config.resultsId);
        this.hideElement(this.config.quickAddFormId);
    }

    /**
     * Confirm selection and call callback
     */
    confirmSelection() {
        if (this.selectedCompany && this.callback) {
            this.callback(this.selectedCompany);
            this.close();
        }
    }

    /**
     * Clear selection (external form)
     */
    clearSelection() {
        // Clear hidden field
        const hiddenField = document.getElementById(this.config.hiddenFieldId);
        if (hiddenField) hiddenField.value = '';

        // Hide selection display
        this.hideElement(this.config.selectedInfoId);
        this.hideElement(this.config.clearBtnId);
    }

    /**
     * Update external form with selected company
     */
    updateExternalForm(company) {
        // Set hidden field
        const hiddenField = document.getElementById(this.config.hiddenFieldId);
        if (hiddenField) {
            hiddenField.value = company.id;
        }

        // Update display
        const displayInfo = document.getElementById(this.config.displayInfoId);
        if (displayInfo) {
            displayInfo.textContent = `${company.name}${company.ticker_symbol ? ' (' + company.ticker_symbol + ')' : ''}`;
        }

        // Show selection info
        this.showElement(this.config.selectedInfoId);
        this.showElement(this.config.clearBtnId);
    }

    /**
     * Clear quick add form
     */
    clearQuickAddForm() {
        const fields = ['newCompanyTicker', 'newCompanyName', 'newCompanyIndustry', 'newCompanySector'];
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) field.value = '';
        });
    }

    /**
     * Utility methods
     */
    showElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) element.style.display = 'block';
    }

    hideElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) element.style.display = 'none';
    }
}

// Global instance and convenience functions for compatibility
let globalCompanySearch = null;

function initializeCompanySearch(config = {}) {
    globalCompanySearch = new CompanySearchComponent(config);
    globalCompanySearch.init();
    return globalCompanySearch;
}

function openCompanyModal(callback) {
    if (globalCompanySearch) {
        globalCompanySearch.open(callback);
    } else {
        console.error('Company search component not initialized');
    }
}

function clearSelectedCompany() {
    if (globalCompanySearch) {
        globalCompanySearch.clearSelection();
    }
}

// Auto-initialize if in a compatible environment
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('companySearchModal')) {
        initializeCompanySearch();
    }
});