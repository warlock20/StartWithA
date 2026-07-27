import { useState, useEffect, useRef } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import { apiGet } from '../../lib/api';
import { TickerValidator } from '../../lib/tickerValidator';

/**
 * Quick-add form for creating a new company inside the search modal.
 * Validates tickers via TickerValidator and auto-fills from Yahoo Finance lookup.
 */
export function QuickAddForm({ prefillQuery, onSubmit }) {
  const [ticker, setTicker] = useState('');
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');
  const [sector, setSector] = useState('');
  const [summary, setSummary] = useState('');
  const [tickerError, setTickerError] = useState('');
  const [nameError, setNameError] = useState('');
  const [tickerHint, setTickerHint] = useState('Formats: AAPL, NYSE:MSFT, SAP.DE, FRA:SAP');
  const [tickerValid, setTickerValid] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const debouncedTicker = useDebounce(ticker, 800);
  const initializedRef = useRef(false);

  // Pre-fill from search query on first render
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    if (!prefillQuery) return;
    const q = prefillQuery.trim().toUpperCase();
    if (q.length <= 5 && /^[A-Z]+$/.test(q)) {
      setTicker(q);
    } else {
      setName(prefillQuery.trim());
    }
  }, [prefillQuery]);

  // Auto-lookup ticker info via Yahoo Finance
  useEffect(() => {
    if (!debouncedTicker || debouncedTicker.length < 2) return;

    const validation = TickerValidator.parseAndValidate(debouncedTicker);
    if (!validation.isValid) return;

    let cancelled = false;

    apiGet(`/companies/api/lookup/${validation.normalizedTicker}`)
      .then((data) => {
        if (cancelled) return;
        if (data.success && data.company_info) {
          const info = data.company_info;
          // Only auto-fill empty fields so we don't overwrite user edits
          if (info.name) setName((prev) => prev || info.name);
          if (info.industry) setIndustry((prev) => prev || info.industry);
          if (info.sector) setSector((prev) => prev || info.sector);
          if (info.summary) setSummary((prev) => prev || info.summary);
        }
      })
      .catch(() => { /* silently fail — user can enter manually */ });

    return () => { cancelled = true; };
  }, [debouncedTicker]);

  function handleTickerChange(e) {
    const val = e.target.value.toUpperCase();
    setTicker(val);
    setTickerError('');

    if (!val) {
      setTickerValid(false);
      setTickerHint('Formats: AAPL, NYSE:MSFT, SAP.DE, FRA:SAP');
      return;
    }

    const validation = TickerValidator.parseAndValidate(val);
    if (!validation.isValid) {
      setTickerValid(false);
      setTickerError(validation.errors.join('; '));
    } else {
      setTickerValid(true);
      setTickerError('');

      let hint = '';
      if (validation.normalizedTicker !== val) {
        hint = `Will be saved as: ${validation.normalizedTicker} (${validation.exchangeName})`;
      } else if (validation.exchangeCode) {
        hint = validation.exchangeName;
      } else {
        hint = 'Formats: AAPL, NYSE:MSFT, SAP.DE, FRA:SAP';
      }
      if (validation.warnings.length > 0) {
        hint += ' \u2014 ' + validation.warnings.join('; ');
      }
      setTickerHint(hint);
    }
  }

  async function handleSubmit() {
    const validation = TickerValidator.parseAndValidate(ticker);
    if (!validation.isValid) {
      setTickerError(validation.errors.join('; '));
      setTickerValid(false);
      return;
    }
    if (!name.trim()) {
      setNameError('Company name is required');
      return;
    }

    setIsSubmitting(true);
    setNameError('');
    setTickerError('');

    const result = await onSubmit({
      ticker_symbol: validation.normalizedTicker,
      name: name.trim(),
      industry: industry.trim() || null,
      sector: sector.trim() || null,
      summary: summary.trim() || null,
    });

    setIsSubmitting(false);

    if (!result.success && result.error) {
      setTickerError(result.error);
    }
  }

  return (
    <div className="border-top pt-3" id="quickAddForm">
      <h6>Add New Company</h6>
      <div className="row">
        <div className="col-md-4">
          <label htmlFor="newCompanyTicker" className="form-label">
            Ticker Symbol <span className="text-danger">*</span>
          </label>
          <input
            type="text"
            className={`form-control${tickerError ? ' is-invalid' : tickerValid ? ' is-valid' : ''}`}
            id="newCompanyTicker"
            placeholder="e.g., AAPL, FRA:SAP"
            style={{ textTransform: 'uppercase' }}
            value={ticker}
            onChange={handleTickerChange}
          />
          {tickerError && <div className="invalid-feedback">{tickerError}</div>}
          {tickerValid && <div className="valid-feedback">Valid ticker format</div>}
          <small className="form-text text-muted" id="tickerHint">{tickerHint}</small>
        </div>
        <div className="col-md-8">
          <label htmlFor="newCompanyName" className="form-label">
            Company Name <span className="text-danger">*</span>
          </label>
          <input
            type="text"
            className={`form-control${nameError ? ' is-invalid' : ''}`}
            id="newCompanyName"
            placeholder="e.g., Apple Inc."
            value={name}
            onChange={(e) => { setName(e.target.value); setNameError(''); }}
          />
          {nameError && <div className="invalid-feedback">{nameError}</div>}
        </div>
      </div>
      <div className="row mt-2">
        <div className="col-md-6">
          <label htmlFor="newCompanyIndustry" className="form-label">Industry (Optional)</label>
          <input
            type="text"
            className="form-control"
            id="newCompanyIndustry"
            placeholder="e.g., Technology"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
        </div>
        <div className="col-md-6">
          <label htmlFor="newCompanySector" className="form-label">Sector (Optional)</label>
          <input
            type="text"
            className="form-control"
            id="newCompanySector"
            placeholder="e.g., Consumer Electronics"
            value={sector}
            onChange={(e) => setSector(e.target.value)}
          />
        </div>
      </div>
      <div className="mt-2">
        <label htmlFor="newCompanySummary" className="form-label">Company Summary (Optional)</label>
        <textarea
          className="form-control"
          id="newCompanySummary"
          rows="3"
          placeholder="Brief description of what the company does..."
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <div className="form-text">A short summary helps with AI-powered analysis in research workflows</div>
      </div>
      <button
        type="button"
        className="btn btn-success mt-2"
        id="addNewCompanyBtn"
        onClick={handleSubmit}
        disabled={isSubmitting}
      >
        {isSubmitting ? (
          <>
            <span className="spinner-border spinner-border-sm me-1" role="status" />
            Creating...
          </>
        ) : 'Add Company'}
      </button>
    </div>
  );
}
