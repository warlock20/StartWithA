import { useEffect, useRef } from 'react';

export function EvidenceDrawer({ evidence, usedIn, onClose }) {
  const closeRef = useRef(null);
  useEffect(() => { if (closeRef.current) closeRef.current.focus(); }, [evidence.label]);

  return (
    <aside className="aic-drawer" aria-label={`Evidence ${evidence.label}`}
           onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}>
      <div className="aic-drawer-head">
        <span className="aic-ref is-active">{evidence.label}</span>
        <button ref={closeRef} type="button" className="btn btn-outline-secondary btn-sm" aria-label="Close evidence"
                onClick={onClose}><i className="bi bi-x-lg" aria-hidden="true" /></button>
      </div>
      <div>
        <div className="aic-muted">{evidence.metric}{evidence.period ? ` · ${evidence.period}` : ''}</div>
        <div className="aic-drawer-value aic-mono">{evidence.value}</div>
      </div>
      <div>
        <span className="aic-eyebrow">Source</span>
        {evidence.source_url
          ? <a href={evidence.source_url} target="_blank" rel="noopener noreferrer">{evidence.source_title}</a>
          : <span>{evidence.source_title}</span>}
        {evidence.location && <div className="aic-muted">{evidence.location}</div>}
      </div>
      <div>
        <span className="aic-eyebrow">Quote</span>
        <blockquote className="aic-drawer-quote">{evidence.quote ? `“${evidence.quote}”` : 'No quote recorded.'}</blockquote>
      </div>
      <span className={`aic-chip ${evidence.verified ? 'aic-chip--ok' : 'aic-chip--warn'}`}>
        {evidence.verified ? 'Quote found in source' : 'Quote not found in source'}
      </span>
      {usedIn.length > 0 && (
        <div>
          <span className="aic-eyebrow">Used in</span>
          <ul className="aic-drawer-used">{usedIn.map((name) => <li key={name}>{name}</li>)}</ul>
        </div>
      )}
    </aside>
  );
}
