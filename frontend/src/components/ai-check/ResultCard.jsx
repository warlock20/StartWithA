import { useState } from 'react';
import { buildAnswerBlocks, insertIntoAnswer } from './answerBlocks';
import { MODE_LABELS, VERDICT_LABELS, formatDate } from './progress';

const VERDICT_CLASS = { satisfied: 'satisfied', not_satisfied: 'not-satisfied', needs_attention: 'attention' };
const STAGE_NAMES = { gathering: 'Gather', extracting: 'Extract', analyzing: 'Analyze' };

export function ResultCard({ run, history, onRetry, onRerun }) {
  const [highlight, setHighlight] = useState([]);
  const [inserted, setInserted] = useState(false);

  if (run.status !== 'completed') {
    return (
      <section className="aic-panel aic-panel--failed" aria-label="AI check result">
        <p className="aic-panel-title">
          {run.status === 'cancelled' ? 'AI check cancelled.' : `AI check failed while ${run.failed_stage || 'running'}.`}
        </p>
        {run.error && <p className="aic-muted">{run.error}</p>}
        <div className="aic-actions">
          {run.status === 'failed' && STAGE_NAMES[run.failed_stage] && (
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              Retry from {STAGE_NAMES[run.failed_stage]}
            </button>
          )}
          <button type="button" className="btn btn-outline-secondary" onClick={onRerun}>New run</button>
        </div>
      </section>
    );
  }

  const r = run.result || {};
  const verdictClass = VERDICT_CLASS[r.suggested_verdict];
  const onInsert = () => setInserted(insertIntoAnswer(buildAnswerBlocks(run)));

  return (
    <section className="aic-result" aria-label="AI check result">
      <div className="aic-result-head">
        <span className="aic-panel-title"><i className="bi bi-stars" aria-hidden="true" /> AI check</span>
        <span className="aic-muted">
          {MODE_LABELS[run.mode]} · {formatDate(run.created_at)}
          {' '}· {(run.sources || []).length} sources · {(run.evidence || []).length} figures · Cost ${run.cost_estimate.toFixed(2)}
        </span>
        <div className="aic-actions">
          <button type="button" className="btn btn-outline-secondary" onClick={onRerun}>Re-run</button>
          <button type="button" className="btn btn-primary" onClick={onInsert}>
            {inserted ? 'Inserted' : 'Insert into answer'}
          </button>
        </div>
      </div>
      <div className="aic-result-body">
        {r.suggested_verdict && (
          <div className={`aic-verdict aic-verdict--${verdictClass}`}>
            <div className="aic-verdict-label">
              <span className="aic-eyebrow">Suggested verdict</span>
              <strong>{VERDICT_LABELS[r.suggested_verdict]}</strong>
            </div>
            <p>{r.verdict_reason} You still choose the verdict below.</p>
          </div>
        )}
        <div><h3 className="aic-eyebrow">Summary</h3><p className="aic-summary">{r.summary}</p></div>
        <div>
          <h3 className="aic-eyebrow">Calculation · click a figure to see its evidence</h3>
          <table className="aic-table aic-calc">
            <tbody>
              {(r.calculation || []).map((line, i) => (
                <tr key={i} className={`is-${line.kind}`}>
                  <td>{line.label}{line.note && <div className="aic-note">{line.note}</div>}</td>
                  <td className="aic-num aic-mono">{line.value}</td>
                  <td className="aic-refs">
                    {line.evidence.map((label) => (
                      <button key={label} type="button"
                              className={`aic-ref${highlight.includes(label) ? ' is-active' : ''}`}
                              onClick={() => setHighlight(line.evidence)}>{label}</button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(r.gaps || []).length > 0 && (
          <div><h3 className="aic-eyebrow">Missing</h3><ul className="aic-gaps">{r.gaps.map((g) => <li key={g}>{g}</li>)}</ul></div>
        )}
        <div>
          <h3 className="aic-eyebrow">Evidence</h3>
          <table className="aic-table aic-evidence">
            <thead><tr><th scope="col">#</th><th scope="col">Metric</th><th scope="col" className="aic-num">Value</th>
              <th scope="col">Source · location</th><th scope="col">Quote</th><th scope="col">Verified</th></tr></thead>
            <tbody>
              {(run.evidence || []).map((e) => (
                <tr key={e.label} className={highlight.includes(e.label) ? 'is-highlighted' : ''}>
                  <td className="aic-strong">{e.label}</td>
                  <td>{e.metric}</td>
                  <td className="aic-num aic-mono">{e.value}</td>
                  <td>{e.source_url
                    ? <a href={e.source_url} target="_blank" rel="noopener noreferrer">{e.source_title}</a>
                    : e.source_title}{e.location ? ` · ${e.location}` : ''}</td>
                  <td className="aic-quote">{e.quote ? `“${e.quote}”` : '—'}</td>
                  <td>{e.verified
                    ? <span className="aic-verified" aria-label="Verified">✓</span>
                    : <span className="aic-chip aic-chip--warn">Unverified</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {history.length > 1 && (
          <div className="aic-history">
            <span className="aic-strong">Earlier runs</span>
            {history.slice(1).map((h) => (
              <span key={h.id} className="aic-chip">
                {formatDate(h.created_at)} · {MODE_LABELS[h.mode]} · {VERDICT_LABELS[h.suggested_verdict] || h.status}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
