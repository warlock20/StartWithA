import { useState } from 'react';
import { normalizeIsin, isValidIsin, invalidIsinMessage } from '../../lib/isin';

const HINT = "12 characters. Find it in the annual report or on the exchange's listing page.";

/**
 * Warns that a selected company has no ISIN and lets the user type one.
 * ISINs come only from the user; nothing here proposes or fetches one.
 */
export function MissingIsinNotice({ value, onValueChange, error: serverError, isSaving, onSave }) {
  const [touched, setTouched] = useState(false);

  const normalized = normalizeIsin(value);
  const valid = normalized.length === 12 && isValidIsin(normalized);
  const showLocal = normalized !== '' && !valid && (normalized.length === 12 || touched);
  const error = (showLocal ? invalidIsinMessage(normalized) : '') || serverError;

  function handleKeyDown(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (valid && !isSaving) onSave();
  }

  return (
    <div className="alert alert-warning mt-3 mb-0" data-testid="missing-isin-notice">
      <h6 className="mb-1">No ISIN for this company</h6>
      <p className="mb-2">
        Our market-data source doesn't give a reliable ISIN, so we don't fill it in for you.
        Without one, market sweeps and imports can't match this company. You can add it now
        or later from the company page.
      </p>
      <label htmlFor="missingIsinInput" className="form-label mb-1">ISIN (optional)</label>
      <div className="input-group">
        <input
          id="missingIsinInput"
          type="text"
          className={`form-control${error ? ' is-invalid' : ''}`}
          style={{ fontFamily: 'monospace', textTransform: 'uppercase' }}
          placeholder="e.g. JP3633400001"
          autoComplete="off"
          value={value}
          onChange={(e) => { setTouched(false); onValueChange(e.target.value); }}
          onBlur={() => setTouched(true)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          className="btn btn-primary"
          data-testid="save-isin"
          disabled={!valid || isSaving}
          onClick={onSave}
        >
          {isSaving ? 'Saving…' : 'Save ISIN'}
        </button>
      </div>
      {error ? (
        <div className="invalid-feedback d-block">{error}</div>
      ) : (
        <div className="form-text">{HINT}</div>
      )}
    </div>
  );
}
