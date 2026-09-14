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
  const [results, setResults] = useState({ yahoo: [], user: [], sweep: [] });
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [sweepMatch, setSweepMatch] = useState(null);
  const [isAdopting, setIsAdopting] = useState(false);

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
      setResults({ yahoo: [], user: [], sweep: [] });
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
        const sweep = data.sweep_companies || [];
        setResults({ yahoo, user, sweep });
        setShowQuickAdd(yahoo.length === 0 && user.length === 0 && sweep.length === 0);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('Search error:', err);
        setResults({ yahoo: [], user: [], sweep: [] });
      })
      .finally(() => {
        if (!cancelled) setIsSearching(false);
      });

    return () => { cancelled = true; };
  }, [debouncedQuery, isOpen]);

  // -----------------------------------------------------------------------
  // Does the selected company match a sweep row that knows its ISIN?
  //
  // Only ever asked for a company that has none. Nothing is written here: the
  // answer is a proposal, and the button below is the human gate. An ISIN
  // written without that click would travel to every user holding it, as a
  // link whose origin claims no judgement was needed.
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!selectedCompany || !selectedCompany.id || selectedCompany.isin) {
      setSweepMatch(null);
      return;
    }

    let cancelled = false;
    apiGet(`/companies/api/companies/${selectedCompany.id}/sweep-match`)
      .then((data) => {
        if (cancelled) return;
        setSweepMatch((data.matches && data.matches[0]) || null);
      })
      .catch(() => { if (!cancelled) setSweepMatch(null); });

    return () => { cancelled = true; };
  }, [selectedCompany]);

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  function resetState() {
    setQuery('');
    setResults({ yahoo: [], user: [], sweep: [] });
    setSelectedCompany(null);
    setShowQuickAdd(false);
    setIsSearching(false);
    setSweepMatch(null);
    setIsAdopting(false);
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
        // Only ever set by a provider that is authoritative for ISINs; Yahoo
        // is not, so this is null in practice today. The server re-checks it
        // regardless -- see _trusted_provider_isin.
        provider_isin: suggestion.isin || null,
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

  async function handleSelectSweep(row) {
    if (window.showToast) window.showToast('Creating\u2026', 'loading');
    try {
      // sweep_company_id is the whole point: the row carries an ISIN a person
      // entered, and picking it is that person saying this is the company.
      const result = await apiPost('/companies/api/companies/create', {
        sweep_company_id: row.sweep_company_id,
        ticker_symbol: row.ticker || '',
        name: row.company_name,
        sector: row.sector_label || null,
      });
      if (result.success) {
        if (window.showToast) window.showToast('Company created', 'success');
        setSelectedCompany(result.company);
      } else if (window.showToast) {
        window.showToast(result.error || 'Failed to create company', 'danger');
      }
    } catch (err) {
      if (window.showToast) window.showToast('Error creating company', 'danger');
      console.error('Error creating company:', err);
    }
  }

  async function handleAdoptIsin() {
    if (!selectedCompany || !sweepMatch) return;
    setIsAdopting(true);
    try {
      const result = await apiPost(
        `/companies/api/companies/${selectedCompany.id}/adopt-isin`,
        { sweep_company_id: sweepMatch.sweep_company_id },
      );
      if (result.success) {
        if (window.showToast) window.showToast('ISIN linked', 'success');
        setSelectedCompany((prev) => ({ ...prev, isin: result.company.isin }));
        setSweepMatch(null);
      } else if (window.showToast) {
        window.showToast(result.error || 'Could not link that ISIN', 'danger');
      }
    } catch (err) {
      if (window.showToast) window.showToast('Could not link that ISIN', 'danger');
      console.error('Error adopting ISIN:', err);
    } finally {
      setIsAdopting(false);
    }
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
  const hasResults = results.yahoo.length > 0 || results.user.length > 0
    || results.sweep.length > 0;

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
                    sweepCompanies={results.sweep}
                    onSelectYahoo={handleSelectYahoo}
                    onSelectUser={handleSelectUser}
                    onSelectSweep={handleSelectSweep}
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
              <>
                <div className="alert alert-success mb-0" id="selectedCompanyDisplay">
                  <h6>Selected Company:</h6>
                  <div id="modalSelectedCompanyInfo">
                    <strong>{selectedCompany.name}</strong><br />
                    <small>
                      Ticker: {selectedCompany.ticker_symbol || 'N/A'} | Industry: {selectedCompany.industry || 'N/A'}
                      {selectedCompany.isin && <> | ISIN: {selectedCompany.isin}</>}
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

                {sweepMatch && (
                  <div className="alert alert-info mt-3 mb-0" data-testid="sweep-match-banner">
                    <h6 className="mb-1">This may be a company we already identify</h6>
                    <p className="mb-2">
                      <strong>{sweepMatch.company_name}</strong>
                      {sweepMatch.ticker && <> ({sweepMatch.ticker})</>} in the{' '}
                      {sweepMatch.sweep_country || sweepMatch.sweep_name} sweep carries
                      ISIN <strong>{sweepMatch.isin}</strong>.
                      {sweepMatch.basis === 'name' && (
                        <>
                          {' '}
                          <span className="text-muted">
                            Matched on name only — check it is the same company.
                          </span>
                        </>
                      )}
                    </p>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      data-testid="adopt-isin"
                      disabled={isAdopting}
                      onClick={handleAdoptIsin}
                    >
                      {isAdopting ? 'Linking\u2026' : 'Use this ISIN'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-link"
                      onClick={() => setSweepMatch(null)}
                    >
                      Not the same company
                    </button>
                  </div>
                )}
              </>
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
