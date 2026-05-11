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
        this.lookupDebounceTimer = null;
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

        // Auto-uppercase ticker field with real-time validation
        const tickerField = document.getElementById('newCompanyTicker');
        if (tickerField) {
            tickerField.addEventListener('input', (e) => {
                const value = e.target.value.toUpperCase();
                e.target.value = value;

                // Real-time validation
                this.validateTickerInput(value);

                // Auto-lookup if valid
                if (typeof TickerValidator !== 'undefined') {
                    const validation = TickerValidator.parseAndValidate(value);
                    if (validation.isValid && value.length >= 2) {
                        clearTimeout(this.lookupDebounceTimer);
                        this.lookupDebounceTimer = setTimeout(() => {
                            this.lookupTickerInfo(validation.normalizedTicker);
                        }, 800);
                    }
                } else {
                    // Fallback to old logic if TickerValidator not loaded
                    const ticker = value.trim();
                    if (ticker.length >= 3 && ticker.length <= 5 && ticker.match(/^[A-Z]+$/)) {
                        clearTimeout(this.lookupDebounceTimer);
                        this.lookupDebounceTimer = setTimeout(() => {
                            this.lookupTickerInfo(ticker);
                        }, 800);
                    }
                }
            });

            // Also validate on blur
            tickerField.addEventListener('blur', (e) => {
                this.validateTickerInput(e.target.value.toUpperCase());
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
            this.hideElement('searchSpinner');
            return;
        }

        // Show loading spinner
        this.showElement('searchSpinner');

        try {
            const response = await fetch(`${this.config.searchEndpoint}?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            this.displaySearchResults(data, query);
        } catch (error) {
            console.error('Search error:', error);
            this.hideElement(this.config.resultsId);
        } finally {
            // Always hide spinner when done
            this.hideElement('searchSpinner');
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
            sector: yahooCompany.sector || null,
            summary: yahooCompany.summary || null
        };

        showToast('Creating…', 'loading');
        try {
            const response = await fetch(this.config.createEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                showToast('Company created', 'success');
                this.selectCompany(result.company);
            } else {
                showToast(result.error || 'Failed to create company', 'danger');
                console.error('Error creating company:', result.error);
                // Show error in UI if possible
                const tickerError = document.getElementById('tickerError');
                if (tickerError) {
                    tickerError.textContent = result.error;
                    tickerError.style.display = 'block';
                }
            }
        } catch (error) {
            showToast('Error creating company', 'danger');
            console.error('Error creating company:', error);
        }
    }

    /**
     * Add new company manually
     */
    async addNewCompany() {
        const tickerInput = document.getElementById('newCompanyTicker').value.trim().toUpperCase();
        const name = document.getElementById('newCompanyName').value.trim();
        const industry = document.getElementById('newCompanyIndustry').value.trim();
        const sector = document.getElementById('newCompanySector').value.trim();
        const summary = document.getElementById('newCompanySummary').value.trim();

        // Validate ticker
        let ticker = tickerInput;
        if (typeof TickerValidator !== 'undefined') {
            const validation = TickerValidator.parseAndValidate(tickerInput);

            if (!validation.isValid) {
                this.showError('tickerError', validation.errors.join('; '));
                const tickerField = document.getElementById('newCompanyTicker');
                if (tickerField) {
                    tickerField.classList.add('is-invalid');
                    tickerField.focus();
                }
                return;
            }

            // Use normalized ticker
            ticker = validation.normalizedTicker;
        } else {
            // Fallback validation
            if (!ticker) {
                this.showError('tickerError', 'Ticker symbol is required');
                return;
            }
        }

        if (!name) {
            this.showError('nameError', 'Company name is required');
            const nameField = document.getElementById('newCompanyName');
            if (nameField) {
                nameField.classList.add('is-invalid');
                nameField.focus();
            }
            return;
        }

        const data = {
            ticker_symbol: ticker,
            name: name,
            industry: industry || null,
            sector: sector || null,
            summary: summary || null
        };

        showToast('Creating…', 'loading');
        try {
            const response = await fetch(this.config.createEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                showToast('Company created', 'success');
                this.selectCompany(result.company);
                this.clearQuickAddForm();
            } else {
                showToast(result.error || 'Failed to create company', 'danger');
                this.showError('tickerError', result.error);
            }
        } catch (error) {
            showToast('Error creating company', 'danger');
            console.error('Error creating company:', error);
            this.showError('tickerError', 'Error creating company. Please try again.');
        }
    }

    /**
     * Show error message in form
     */
    showError(errorElementId, message) {
        const errorElement = document.getElementById(errorElementId);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
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
        const fields = ['newCompanyTicker', 'newCompanyName', 'newCompanyIndustry', 'newCompanySector', 'newCompanySummary'];
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) field.value = '';
        });

        // Clear validation states
        const tickerInput = document.getElementById('newCompanyTicker');
        if (tickerInput) {
            tickerInput.classList.remove('is-valid', 'is-invalid');
        }
    }

    /**
     * Validate ticker input and show feedback
     */
    validateTickerInput(ticker) {
        const tickerInput = document.getElementById('newCompanyTicker');
        const tickerError = document.getElementById('tickerError');
        const tickerHint = document.getElementById('tickerHint');

        if (!tickerInput) return false;

        if (!ticker) {
            // Empty - neutral state
            tickerInput.classList.remove('is-valid', 'is-invalid');
            return false;
        }

        // Check if TickerValidator is loaded
        if (typeof TickerValidator === 'undefined') {
            // Fallback validation
            return true;
        }

        const validation = TickerValidator.parseAndValidate(ticker);

        // Remove previous states
        tickerInput.classList.remove('is-valid', 'is-invalid');

        if (!validation.isValid) {
            // Show error
            tickerInput.classList.add('is-invalid');
            if (tickerError) {
                tickerError.textContent = validation.errors.join('; ');
            }
            return false;
        }

        // Valid - show success
        tickerInput.classList.add('is-valid');

        // Show normalized format and exchange
        if (tickerHint) {
            if (validation.normalizedTicker !== ticker) {
                tickerHint.innerHTML = `<span class="text-success">Will be saved as: <strong>${validation.normalizedTicker}</strong> (${validation.exchangeName})</span>`;
            } else if (validation.exchangeCode) {
                tickerHint.innerHTML = `<span class="text-muted">${validation.exchangeName}</span>`;
            } else {
                tickerHint.innerHTML = `<span class="text-muted">Formats: AAPL, NYSE:MSFT, SAP.DE, FRA:SAP</span>`;
            }

            // Show warnings if any
            if (validation.warnings.length > 0) {
                const warningText = validation.warnings.join('; ');
                tickerHint.innerHTML += `<br><span class="text-warning">${warningText}</span>`;
            }
        }

        return true;
    }

    /**
     * Lookup company info via yfinance API
     */
    async lookupTickerInfo(ticker) {
        // Show loading state on ticker field
        const tickerField = document.getElementById('newCompanyTicker');
        if (tickerField) {
            tickerField.style.backgroundImage = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'20\' height=\'20\' viewBox=\'0 0 50 50\'%3E%3Cpath fill=\'%230d6efd\' d=\'M25 5A20 20 0 1 0 45 25 20 20 0 0 0 25 5zm0 36A16 16 0 1 1 41 25 16 16 0 0 1 25 41z\' opacity=\'.3\'/%3E%3Cpath fill=\'%230d6efd\' d=\'M25 5v4A16 16 0 0 1 41 25h4A20 20 0 0 0 25 5z\'%3E%3CanimateTransform attributeName=\'transform\' type=\'rotate\' from=\'0 25 25\' to=\'360 25 25\' dur=\'0.8s\' repeatCount=\'indefinite\'/%3E%3C/path%3E%3C/svg%3E")';
            tickerField.style.backgroundRepeat = 'no-repeat';
            tickerField.style.backgroundPosition = 'right 10px center';
            tickerField.style.backgroundSize = '20px';
        }

        try {
            const response = await fetch(`/companies/api/lookup/${ticker}`);
            const data = await response.json();

            if (data.success) {
                console.log('Auto-filled company data:', data.company_info);
                this.fillCompanyForm(data.company_info);

                // Show success indicator
                this.showLookupSuccess(ticker);
            } else {
                // Silently fail - user can still enter manually
                console.log('Ticker lookup failed:', data.error);
            }
        } catch (error) {
            console.error('Ticker lookup error:', error);
            // Silently fail - don't interrupt user experience
        } finally {
            // Remove loading state
            if (tickerField) {
                tickerField.style.backgroundImage = '';
            }
        }
    }

    /**
     * Fill company form with fetched data
     */
    fillCompanyForm(companyInfo) {
        const fields = {
            'newCompanyName': companyInfo.name,
            'newCompanyIndustry': companyInfo.industry,
            'newCompanySector': companyInfo.sector,
            'newCompanySummary': companyInfo.summary
        };

        Object.entries(fields).forEach(([fieldId, value]) => {
            const field = document.getElementById(fieldId);
            if (field && value) {
                field.value = value;
                // Add visual feedback
                field.style.backgroundColor = '#d4edda';
                setTimeout(() => {
                    field.style.backgroundColor = '';
                }, 2000);
            }
        });
    }

    /**
     * Show lookup success indicator
     */
    showLookupSuccess(ticker) {
        const tickerField = document.getElementById('newCompanyTicker');
        if (tickerField) {
            const originalBorder = tickerField.style.border;
            tickerField.style.border = '2px solid #28a745';
            tickerField.title = `Auto-filled from ${ticker} data`;

            setTimeout(() => {
                tickerField.style.border = originalBorder;
                tickerField.title = '';
            }, 3000);
        }
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