import { useState, useEffect, useRef } from 'react';
import { apiPost } from '../../lib/api';

/**
 * Company Tagging Modal — React island replacement for company-tagging.js.
 *
 * Detects company mentions in text, shows a modal with high/medium confidence
 * suggestions as checkboxes, and links selected companies to notes or snippets.
 *
 * Registers `window.detectAndSuggestCompanies(text, targetType, targetId, onComplete)`
 * on mount, which is called imperatively by sector-canvas.js after saving a note.
 */
export function CompanyTaggingModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [suggestions, setSuggestions] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [isLinking, setIsLinking] = useState(false);

  const targetRef = useRef({ type: null, id: null });
  const onCompleteRef = useRef(null);
  const modalElRef = useRef(null);
  const bsModalRef = useRef(null);

  // -----------------------------------------------------------------------
  // Register global imperative API
  // -----------------------------------------------------------------------
  useEffect(() => {
    window.detectAndSuggestCompanies = async (text, targetType, targetId, onComplete) => {
      try {
        const data = await apiPost('/sectors/detect-companies', { text });

        if (data.success && data.suggestions && data.suggestions.total_matches > 0) {
          targetRef.current = { type: targetType, id: targetId };
          onCompleteRef.current = onComplete;

          const high = data.suggestions.high_confidence || [];
          const medium = data.suggestions.medium_confidence || [];

          setSuggestions({ high, medium });
          setSelected(new Set(high.map((c) => c.id)));
          setIsOpen(true);
        } else {
          console.log('No company mentions detected');
          if (onComplete) onComplete();
        }
      } catch (err) {
        console.error('Error detecting companies:', err);
        if (window.showToast) window.showToast('Error detecting companies', 'danger');
        if (onComplete) onComplete();
      }
    };

    return () => { delete window.detectAndSuggestCompanies; };
  }, []);

  // -----------------------------------------------------------------------
  // Bootstrap Modal lifecycle
  // -----------------------------------------------------------------------
  useEffect(() => {
    const el = modalElRef.current;
    if (!el || !window.bootstrap) return;

    bsModalRef.current = new window.bootstrap.Modal(el);

    const onHidden = () => {
      setIsOpen(false);
      setSuggestions(null);
      setSelected(new Set());
      setIsLinking(false);
    };
    el.addEventListener('hidden.bs.modal', onHidden);
    return () => el.removeEventListener('hidden.bs.modal', onHidden);
  }, []);

  useEffect(() => {
    if (!bsModalRef.current) return;
    if (isOpen) bsModalRef.current.show();
  }, [isOpen]);

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  function close() {
    bsModalRef.current?.hide();
  }

  function runOnComplete() {
    if (onCompleteRef.current) {
      setTimeout(() => {
        onCompleteRef.current();
        onCompleteRef.current = null;
      }, 300);
    }
  }

  function toggleCompany(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleLink() {
    const { type, id } = targetRef.current;
    const companyIds = Array.from(selected);

    if (companyIds.length === 0) {
      if (window.showToast) window.showToast('Select at least one company', 'warning');
      return;
    }

    setIsLinking(true);
    try {
      const endpoint = type === 'note'
        ? `/sectors/note/${id}/link-companies`
        : `/sectors/snippet/${id}/link-companies`;

      const data = await apiPost(endpoint, { company_ids: companyIds });

      if (data.success) {
        if (window.showToast) {
          window.showToast(
            `Linked ${companyIds.length} ${companyIds.length === 1 ? 'company' : 'companies'}`,
            'success',
          );
        }

        if (window.updateLinkedCompaniesDisplay) {
          window.updateLinkedCompaniesDisplay(type, id, data.linked_companies);
        }

        close();
        runOnComplete();
      } else {
        if (window.showToast) window.showToast(data.error || 'Failed to link companies', 'danger');
      }
    } catch (err) {
      console.error('Error linking companies:', err);
      if (window.showToast) window.showToast('Error linking companies', 'danger');
    } finally {
      setIsLinking(false);
    }
  }

  function handleSkip() {
    close();
    runOnComplete();
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  const tickerStyle = {
    display: 'inline-block',
    backgroundColor: '#e0e7ff',
    color: '#4338ca',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: '0.75rem',
    fontWeight: 600,
    fontFamily: "'SF Mono', Monaco, monospace",
  };

  const sectorBadgeStyle = {
    display: 'inline-block',
    backgroundColor: '#f3f4f6',
    color: '#6b7280',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: '0.7rem',
    marginLeft: 4,
  };

  function renderItem(company) {
    const checked = selected.has(company.id);
    return (
      <div
        key={company.id}
        onClick={() => toggleCompany(company.id)}
        style={{
          padding: 10,
          border: `1px solid ${checked ? '#3b82f6' : '#e5e7eb'}`,
          borderRadius: 8,
          marginBottom: 8,
          cursor: 'pointer',
          backgroundColor: checked ? '#eff6ff' : 'transparent',
          transition: 'all 0.2s',
        }}
      >
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            checked={checked}
            onChange={() => toggleCompany(company.id)}
            onClick={(e) => e.stopPropagation()}
          />
          <label className="form-check-label" style={{ cursor: 'pointer', width: '100%' }}>
            <div className="fw-bold">{company.name}</div>
            <div className="mt-1">
              <span style={tickerStyle}>{company.ticker}</span>
              {company.sector && <span style={sectorBadgeStyle}>{company.sector}</span>}
            </div>
            <div className="mt-1">
              <small className="text-muted">
                Matched: &ldquo;<em>{company.matched_text}</em>&rdquo;
              </small>
            </div>
          </label>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={modalElRef}
      className="modal fade"
      id="companySuggestionsModal"
      tabIndex="-1"
      aria-hidden="true"
    >
      <div className="modal-dialog modal-dialog-centered modal-dialog-scrollable">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">
              <i className="bi bi-building" /> Link Companies
            </h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" />
          </div>

          <div className="modal-body">
            {suggestions ? (
              <div>
                <p className="text-muted mb-3">
                  <i className="bi bi-info-circle" />{' '}
                  We found mentions of the following companies. Select which ones to link:
                </p>

                {suggestions.high.length > 0 && (
                  <div className="mb-3">
                    <h6 className="fw-bold mb-2">
                      <i className="bi bi-check-circle-fill text-success" /> High Confidence
                    </h6>
                    {suggestions.high.map(renderItem)}
                  </div>
                )}

                {suggestions.medium.length > 0 && (
                  <div className="mb-3">
                    <h6 className="fw-bold mb-2">
                      <i className="bi bi-exclamation-circle-fill text-warning" /> Possible Matches
                    </h6>
                    {suggestions.medium.map(renderItem)}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-4">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Analyzing...</span>
                </div>
                <p className="mt-2 text-muted">Detecting company mentions...</p>
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={handleSkip}>
              <i className="bi bi-skip-forward" /> Skip
            </button>
            <button
              type="button"
              className="btn btn-primary"
              id="linkSelectedCompaniesBtn"
              onClick={handleLink}
              disabled={isLinking || selected.size === 0}
            >
              {isLinking ? (
                <>
                  <span className="spinner-border spinner-border-sm me-1" />
                  Linking...
                </>
              ) : (
                <>
                  <i className="bi bi-link-45deg" /> Link Selected
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
