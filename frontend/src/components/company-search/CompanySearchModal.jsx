import { useState, useEffect, useRef } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import { apiGet, apiPost } from '../../lib/api';
import { SearchResults } from './SearchResults';
import { QuickAddForm } from './QuickAddForm';

/**
 * Company Search Modal — React island replacement for company-search.js.
 *
 * Renders a Bootstrap 5 modal with:
 *   - Debounced search (Yahoo Finance suggestions + user companies)
 *   - Quick-add form with ticker validation and auto-fill from Yahoo lookup
 *   - Company selection + confirm flow
 *
 * Registers `window.openCompanyModal(callback)` on mount so external
 * template code (onclick handlers) can open the modal imperatively.
 */
export function CompanySearchModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ yahoo: [], user: [] });
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  const callbackRef = useRef(null);
  const modalElRef = useRef(null);
  const bsModalRef = useRef(null);
  const searchInputRef = useRef(null);

  const debouncedQuery = useDebounce(query, 300);

  // -----------------------------------------------------------------------
  // Register global imperative API
  // -----------------------------------------------------------------------
  useEffect(() => {
    window.openCompanyModal = (cb) => {
      callbackRef.current = cb;
      setIsOpen(true);
    };
    return () => { delete window.openCompanyModal; };
  }, []);

  // -----------------------------------------------------------------------
  // Bootstrap Modal lifecycle
  // -----------------------------------------------------------------------
  useEffect(() => {
    const el = modalElRef.current;
    if (!el || !window.bootstrap) return;

    bsModalRef.current = new window.bootstrap.Modal(el, {
      backdrop: true,
      keyboard: true,
    });

    const onHidden = () => {
      setIsOpen(false);
      resetState();
    };
    el.addEventListener('hidden.bs.modal', onHidden);
    return () => el.removeEventListener('hidden.bs.modal', onHidden);
  }, []);

  useEffect(() => {
    if (!bsModalRef.current) return;
    if (isOpen) {
      bsModalRef.current.show();
      // Focus search input after modal transition
      setTimeout(() => searchInputRef.current?.focus(), 200);
    }
  }, [isOpen]);

  // -----------------------------------------------------------------------
  // Search when debounced query changes
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;
    if (debouncedQuery.length < 2) {
      setResults({ yahoo: [], user: [] });
      setShowQuickAdd(false);
      return;
    }

    let cancelled = false;
    setIsSearching(true);

    apiGet(`/companies/api/companies/search?q=${encodeURIComponent(debouncedQuery)}`)
      .then((data) => {
        if (cancelled) return;
        const yahoo = data.yahoo_suggestions || [];
        const user = data.user_companies || [];
        setResults({ yahoo, user });
        setShowQuickAdd(yahoo.length === 0 && user.length === 0);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('Search error:', err);
        setResults({ yahoo: [], user: [] });
      })
      .finally(() => {
        if (!cancelled) setIsSearching(false);
      });

    return () => { cancelled = true; };
  }, [debouncedQuery, isOpen]);

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  function resetState() {
    setQuery('');
    setResults({ yahoo: [], user: [] });
    setSelectedCompany(null);
    setShowQuickAdd(false);
    setIsSearching(false);
    callbackRef.current = null;
  }

  function close() {
    bsModalRef.current?.hide();
  }

  async function handleSelectYahoo(suggestion) {
    if (window.showToast) window.showToast('Creating\u2026', 'loading');
    try {
      const result = await apiPost('/companies/api/companies/create', {
        ticker_symbol: suggestion.ticker_symbol,
        name: suggestion.name,
        industry: suggestion.industry || null,
        sector: suggestion.sector || null,
        summary: suggestion.summary || null,
      });
      if (result.success) {
        if (window.showToast) window.showToast('Company created', 'success');
        setSelectedCompany(result.company);
      } else {
        if (window.showToast) window.showToast(result.error || 'Failed to create company', 'danger');
      }
    } catch (err) {
      if (window.showToast) window.showToast('Error creating company', 'danger');
      console.error('Error creating company:', err);
    }
  }

  function handleSelectUser(company) {
    setSelectedCompany(company);
  }

  async function handleQuickAdd(formData) {
    if (window.showToast) window.showToast('Creating\u2026', 'loading');
    try {
      const result = await apiPost('/companies/api/companies/create', formData);
      if (result.success) {
        if (window.showToast) window.showToast('Company created', 'success');
        setSelectedCompany(result.company);
        return { success: true };
      }
      if (window.showToast) window.showToast(result.error || 'Failed to create company', 'danger');
      return { success: false, error: result.error };
    } catch (err) {
      if (window.showToast) window.showToast('Error creating company', 'danger');
      console.error('Error creating company:', err);
      return { success: false, error: 'Error creating company. Please try again.' };
    }
  }

  function handleConfirm() {
    if (selectedCompany && callbackRef.current) {
      callbackRef.current(selectedCompany);
    }
    close();
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  const hasResults = results.yahoo.length > 0 || results.user.length > 0;

  return (
    <div
      ref={modalElRef}
      className="modal fade"
      id="companySearchModal"
      tabIndex="-1"
      aria-labelledby="companySearchModalLabel"
      aria-hidden="true"
    >
      <div className="modal-dialog modal-lg">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title" id="companySearchModalLabel">Select Company</h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Close" />
          </div>

          <div className="modal-body">
            {!selectedCompany ? (
              <>
                {/* Search Input */}
                <div className="mb-3">
                  <label htmlFor="companySearch" className="form-label">
                    Search by ticker symbol or company name
                  </label>
                  <div className="position-relative">
                    <input
                      ref={searchInputRef}
                      type="text"
                      className="form-control"
                      id="companySearch"
                      placeholder="e.g., AAPL, Apple Inc, Microsoft..."
                      autoComplete="off"
                      value={query}
                      onChange={(e) => {
                        setQuery(e.target.value);
                        setSelectedCompany(null);
                        setShowQuickAdd(false);
                      }}
                    />
                    {isSearching && (
                      <div className="position-absolute top-50 end-0 translate-middle-y me-3" id="searchSpinner">
                        <div className="spinner-border spinner-border-sm text-primary" role="status">
                          <span className="visually-hidden">Searching...</span>
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="form-text">Start typing to search existing companies or add a new one</div>
                </div>

                {/* Search Results */}
                {hasResults && !showQuickAdd && (
                  <SearchResults
                    yahooSuggestions={results.yahoo}
                    userCompanies={results.user}
                    onSelectYahoo={handleSelectYahoo}
                    onSelectUser={handleSelectUser}
                  />
                )}

                {/* Quick Add Form */}
                {showQuickAdd && (
                  <QuickAddForm
                    prefillQuery={query}
                    onSubmit={handleQuickAdd}
                  />
                )}

                {/* Toggle to manual add when results exist */}
                {hasResults && !showQuickAdd && (
                  <button
                    type="button"
                    className="btn btn-sm btn-link mt-2 p-0"
                    onClick={() => setShowQuickAdd(true)}
                  >
                    Don't see your company? Add manually
                  </button>
                )}
              </>
            ) : (
              /* Selected Company Display */
              <div className="alert alert-success mb-0" id="selectedCompanyDisplay">
                <h6>Selected Company:</h6>
                <div id="modalSelectedCompanyInfo">
                  <strong>{selectedCompany.name}</strong><br />
                  <small>
                    Ticker: {selectedCompany.ticker_symbol || 'N/A'} | Industry: {selectedCompany.industry || 'N/A'}
                  </small>
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary mt-2"
                  onClick={() => setSelectedCompany(null)}
                >
                  Change Selection
                </button>
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button
              type="button"
              className="btn btn-primary"
              id="confirmCompanySelection"
              disabled={!selectedCompany}
              onClick={handleConfirm}
            >
              Select Company
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
