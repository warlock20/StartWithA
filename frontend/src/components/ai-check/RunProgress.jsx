import { stageStates, MODE_LABELS } from './progress';

const STATUS_TEXT = { queued: 'Queued', running: 'Reading…', done: 'Done', no_figures: 'No figures', failed: 'Failed' };

export function RunProgress({ run, onCancel }) {
  const sources = run.sources || [];
  const extracted = sources.filter((s) => !['queued', 'running'].includes(s.extract_status)).length;
  return (
    <section className="aic-panel" aria-label="AI check progress" aria-live="polite">
      <div className="aic-panel-head">
        <span className="aic-spinner" aria-hidden="true" />
        <span className="aic-panel-title">AI check running · {MODE_LABELS[run.mode]}</span>
        <button type="button" className="btn btn-outline-secondary btn-sm" onClick={onCancel}>Cancel run</button>
      </div>
      <ol className="aic-stages">
        {stageStates(run).map((s) => (
          <li key={s.key} className={`aic-stage is-${s.state}`}>
            <span className="aic-stage-title">{s.label}{s.key === 'extract' && sources.length ? ` · ${extracted} of ${sources.length}` : ''}</span>
          </li>
        ))}
      </ol>
      {sources.length > 0 && (
        <table className="aic-table">
          <thead><tr><th scope="col">Source</th><th scope="col">Type</th><th scope="col">From</th><th scope="col" className="aic-num">Extract</th></tr></thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>{s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> : s.title}</td>
                <td>{s.doc_type || '—'}</td>
                <td>{s.kind === 'web'
                  ? <span className="aic-chip aic-chip--web">Web{s.gap_filled ? ` · fills gap: ${s.gap_filled}` : ''}</span>
                  : <span className="aic-chip">Your document</span>}</td>
                <td className={`aic-num aic-extract is-${s.extract_status}`}>
                  {STATUS_TEXT[s.extract_status]}{s.extract_status === 'done' ? ` · ${s.evidence_count} figures` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="aic-muted">You can leave this page. The run keeps going and the result appears here when you come back.</p>
    </section>
  );
}
