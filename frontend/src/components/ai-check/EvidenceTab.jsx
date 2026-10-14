import { useId, useState } from 'react';
import { filterEvidence } from './resultView';

const PAGE = 20;

export function EvidenceTab({ evidence, activeLabel, onShowEvidence }) {
  const [query, setQuery] = useState('');
  const [unverifiedOnly, setUnverifiedOnly] = useState(false);
  const [limit, setLimit] = useState(PAGE);
  const searchId = useId();

  if (!evidence.length) return <p className="aic-muted">No figures were extracted.</p>;
  const rows = filterEvidence(evidence, { query, unverifiedOnly });
  const shown = rows.slice(0, limit);
  const remaining = rows.length - shown.length;

  return (
    <div className="aic-evidence-tab">
      <div className="aic-evidence-tools">
        <label htmlFor={searchId} className="aic-muted">Search</label>
        <input id={searchId} type="search" className="form-control form-control-sm aic-search"
               placeholder="Metric, period or quote" value={query}
               onChange={(e) => { setQuery(e.target.value); setLimit(PAGE); }} />
        <button type="button" className={`aic-toggle${unverifiedOnly ? ' is-on' : ''}`} aria-pressed={unverifiedOnly}
                onClick={() => { setUnverifiedOnly((value) => !value); setLimit(PAGE); }}>Unverified only</button>
        <span className="aic-muted aic-count">Showing {shown.length} of {rows.length}</span>
      </div>
      <div className="aic-scroll-x">
        <table className="aic-table aic-evidence">
          <thead>
            <tr><th scope="col">#</th><th scope="col">Metric</th><th scope="col">Period</th>
              <th scope="col" className="aic-num">Value</th><th scope="col">Source</th><th scope="col">Verified</th></tr>
          </thead>
          <tbody>
            {shown.map((e) => (
              <tr key={e.label}>
                <td>
                  <button type="button" className={`aic-ref${e.label === activeLabel ? ' is-active' : ''}`}
                          onClick={() => onShowEvidence(e.label)}>{e.label}</button>
                </td>
                <td>{e.metric}</td>
                <td className="aic-muted">{e.period}</td>
                <td className="aic-num aic-mono">{e.value}</td>
                <td>{e.source_title}</td>
                <td>{e.verified
                  ? <span className="aic-verified" aria-label="Verified">✓</span>
                  : <span className="aic-chip aic-chip--warn">Unverified</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="aic-muted">No figures match.</p>}
      {remaining > 0 && (
        <button type="button" className="btn btn-outline-secondary aic-more" onClick={() => setLimit((n) => n + PAGE)}>
          Show {Math.min(PAGE, remaining)} more
        </button>
      )}
    </div>
  );
}
