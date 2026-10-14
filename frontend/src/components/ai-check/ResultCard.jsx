import { useId, useRef, useState } from 'react';
import { buildAnswerBlocks, insertIntoAnswer } from './answerBlocks';
import { CalculationTab } from './CalculationTab';
import { EvidenceDrawer } from './EvidenceDrawer';
import { EvidenceTab } from './EvidenceTab';
import { MODE_LABELS, VERDICT_LABELS, formatDate } from './progress';
import { defaultTab, isLongText, keyFigures, usedIn } from './resultView';

const VERDICT_CLASS = { satisfied: 'satisfied', not_satisfied: 'not-satisfied', needs_attention: 'attention' };
const STAGE_NAMES = { gathering: 'Gather', extracting: 'Extract', analyzing: 'Analyze' };

function SummaryTab({ result }) {
  const [more, setMore] = useState(false);
  const long = isLongText(result.summary);
  return (
    <div className="aic-summary-tab">
      <p className={`aic-summary${long && !more ? ' is-clamped' : ''}`}>{result.summary}</p>
      {long && (
        <button type="button" className="btn btn-link aic-link" onClick={() => setMore((v) => !v)}>
          {more ? 'Show less' : 'Read more'}
        </button>
      )}
      {result.suggested_verdict && result.verdict_reason && (
        <div><h3 className="aic-eyebrow">Why this verdict</h3><p className="aic-body">{result.verdict_reason}</p></div>
      )}
      {(result.gaps || []).length > 0 && (
        <div><h3 className="aic-eyebrow">Missing</h3><ul className="aic-gaps">{result.gaps.map((g) => <li key={g}>{g}</li>)}</ul></div>
      )}
    </div>
  );
}

function SourcesTab({ sources }) {
  if (!sources.length) return <p className="aic-muted">No sources recorded.</p>;
  return (
    <ul className="aic-sources">
      {sources.map((s) => (
        <li key={s.id} className="aic-source">
          <span className={`aic-chip${s.kind === 'web' ? ' aic-chip--web' : ''}`}>{s.kind === 'web' ? 'Web' : 'Document'}</span>
          {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> : <span>{s.title}</span>}
          {s.extract_status === 'failed'
            ? <span className="aic-chip aic-chip--warn">Failed</span>
            : <span className="aic-muted aic-source-count">{s.evidence_count || 0} figures</span>}
        </li>
      ))}
    </ul>
  );
}

export function ResultCard({ run, history, onRetry, onRerun, busy = false }) {
  const [inserted, setInserted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState(() => defaultTab(run.result));
  const [drawerLabel, setDrawerLabel] = useState(null);
  const tabRefs = useRef({});
  const baseId = useId();

  if (run.status !== 'completed') {
    return (
      <section className="aic-panel aic-panel--failed" aria-label="AI check result">
        <p className="aic-panel-title">
          {run.status === 'cancelled' ? 'AI check cancelled.' : `AI check failed while ${run.failed_stage || 'running'}.`}
        </p>
        {run.error && <p className="aic-muted">{run.error}</p>}
        <div className="aic-actions">
          {run.status === 'failed' && STAGE_NAMES[run.failed_stage] && (
            <button type="button" className="btn btn-primary" onClick={onRetry} disabled={busy}>
              Retry from {STAGE_NAMES[run.failed_stage]}
            </button>
          )}
          <button type="button" className="btn btn-outline-secondary" onClick={onRerun}>New run</button>
        </div>
      </section>
    );
  }

  const r = run.result || {};
  const evidence = run.evidence || [];
  const sources = run.sources || [];
  const unverified = evidence.filter((e) => !e.verified).length;
  const figures = keyFigures(r);
  const drawerEvidence = evidence.find((e) => e.label === drawerLabel) || null;
  const showEvidence = (label) => setDrawerLabel(evidence.some((e) => e.label === label) ? label : null);
  const onInsert = () => setInserted(insertIntoAnswer(buildAnswerBlocks(run)));

  const tabs = [
    { key: 'summary', label: 'Summary' },
    { key: 'calculation', label: 'Calculation' },
    { key: 'evidence', label: `Evidence · ${evidence.length}` },
    { key: 'sources', label: `Sources · ${sources.length}` },
  ];
  const onTabKey = (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    const index = tabs.findIndex((t) => t.key === tab);
    const next = tabs[(index + step + tabs.length) % tabs.length].key;
    setTab(next);
    if (tabRefs.current[next]) tabRefs.current[next].focus();
  };

  return (
    <section className="aic-result" aria-label="AI check result">
      <div className="aic-result-head">
        <span className="aic-panel-title"><i className="bi bi-stars" aria-hidden="true" /> AI check</span>
        <span className="aic-muted">
          {MODE_LABELS[run.mode]} · {formatDate(run.created_at)} · {sources.length} sources
          {' '}· {evidence.length} figures{unverified ? ` (${unverified} unverified)` : ''} · Cost ${run.cost_estimate.toFixed(2)}
        </span>
        <div className="aic-actions">
          <button type="button" className="btn btn-link aic-link" aria-expanded={!collapsed}
                  onClick={() => { setCollapsed((v) => !v); setDrawerLabel(null); }}>
            {collapsed ? 'Show details' : 'Collapse'}
          </button>
          <button type="button" className="btn btn-outline-secondary" onClick={onRerun}>Re-run</button>
          <button type="button" className="btn btn-primary" onClick={onInsert}>
            {inserted ? 'Inserted' : 'Insert into answer'}
          </button>
        </div>
      </div>

      <div className="aic-headline">
        {r.suggested_verdict ? (
          <div className={`aic-verdict-box aic-verdict--${VERDICT_CLASS[r.suggested_verdict]}`}>
            <span className="aic-eyebrow">Suggested verdict</span>
            <strong>{VERDICT_LABELS[r.suggested_verdict]}</strong>
          </div>
        ) : (
          <div className="aic-verdict-box aic-verdict-box--none">
            <span className="aic-eyebrow">No suggestion</span>
            <span className="aic-muted">No rubric line matched. Add or complete the verdict rubric for this question to get a suggestion.</span>
          </div>
        )}
        <div className="aic-headline-main">
          {r.headline && <p className="aic-headline-text">{r.headline}</p>}
          {figures.length > 0 && (
            <div className="aic-figures">
              {figures.map((f, i) => (
                <div key={i} className="aic-figure">
                  <span className="aic-figure-label">{f.label}</span>
                  <span className="aic-figure-value aic-mono">{f.value}</span>
                </div>
              ))}
            </div>
          )}
          <span className="aic-muted">You still choose the verdict below.</span>
        </div>
      </div>

      {!collapsed && (
        <>
          <div className="aic-tabs" role="tablist" aria-label="AI check result sections" onKeyDown={onTabKey}>
            {tabs.map((t) => (
              <button key={t.key} ref={(el) => { tabRefs.current[t.key] = el; }} type="button" role="tab"
                      id={`${baseId}-tab-${t.key}`} aria-selected={tab === t.key} aria-controls={`${baseId}-panel`}
                      tabIndex={tab === t.key ? 0 : -1}
                      className={`aic-tab${tab === t.key ? ' is-active' : ''}`} onClick={() => setTab(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="aic-tab-panel" role="tabpanel" id={`${baseId}-panel`} aria-labelledby={`${baseId}-tab-${tab}`}>
            {tab === 'summary' && <SummaryTab result={r} />}
            {tab === 'calculation' && (
              <CalculationTab calculation={r.calculation || []} activeLabel={drawerLabel} onShowEvidence={showEvidence} />
            )}
            {tab === 'evidence' && (
              <EvidenceTab evidence={evidence} activeLabel={drawerLabel} onShowEvidence={showEvidence} />
            )}
            {tab === 'sources' && <SourcesTab sources={sources} />}
          </div>
          {history.length > 1 && (
            <div className="aic-history">
              <span className="aic-strong">Earlier runs</span>
              {history.slice(1).map((h) => (
                <span key={h.id} className="aic-chip">
                  {formatDate(h.created_at)} · {MODE_LABELS[h.mode]} · {VERDICT_LABELS[h.suggested_verdict] || (h.status === 'completed' ? 'No suggestion' : h.status)}
                </span>
              ))}
            </div>
          )}
          {drawerEvidence && (
            <EvidenceDrawer evidence={drawerEvidence} usedIn={usedIn(drawerEvidence.label, r.calculation)}
                            onClose={() => setDrawerLabel(null)} />
          )}
        </>
      )}
    </section>
  );
}
