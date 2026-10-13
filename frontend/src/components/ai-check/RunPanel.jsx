import { useState } from 'react';

const MODES = [
  { value: 'documents', label: 'My documents', hint: 'Only the files you tick. No web. Page references.' },
  { value: 'web', label: 'Web research', hint: 'The AI finds and reads filings itself.' },
  { value: 'both', label: 'Both', hint: 'Your documents first; web only for gaps.' },
];

const DEPTHS = [
  { value: 'full', label: 'Full', hint: 'Gather → Extract → Analyze. Every figure cited and checked.' },
  { value: 'quick', label: 'Quick', hint: 'One call. Faster and cheaper; figures are not checked against sources.' },
];

export function RunPanel({ documents, setups = [], onRun, onCancel, busy = false }) {
  const [mode, setMode] = useState(documents.length ? 'both' : 'web');
  const [depth, setDepth] = useState('full');
  const [setup, setSetup] = useState(setups[0]?.key || 'my_setup');
  const chosen = setups.find((s) => s.key === setup);
  // Only the server-suggested annual report is pre-ticked; with none, nothing is (Both then runs web-only).
  const [picked, setPicked] = useState(() => documents.filter((d) => d.suggested).map((d) => d.id));
  const needsDocs = mode !== 'web';
  const canRun = mode !== 'documents' || picked.length > 0;
  const toggle = (id) => setPicked((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  return (
    <section className="aic-panel" aria-label="AI check run panel">
      <div className="aic-panel-section">
        <span className="aic-eyebrow">Sources</span>
        <div className="aic-modes" role="radiogroup" aria-label="Source mode">
          {MODES.map((m) => (
            <label key={m.value} className={`aic-mode${mode === m.value ? ' is-selected' : ''}`}>
              <span className="aic-mode-title">
                <input type="radio" name="aic-mode" value={m.value} checked={mode === m.value}
                       onChange={() => setMode(m.value)} disabled={m.value !== 'web' && !documents.length} />
                {m.label}
              </span>
              <span className="aic-mode-hint">{m.hint}</span>
            </label>
          ))}
        </div>
      </div>
      {needsDocs && (
        <fieldset className="aic-panel-section aic-docs">
          <legend className="aic-eyebrow">Your documents</legend>
          {documents.length === 0 && <p className="aic-muted">No documents uploaded for this company.</p>}
          {documents.map((d) => (
            <label key={d.id} className="aic-doc">
              <input type="checkbox" checked={picked.includes(d.id)} onChange={() => toggle(d.id)} />
              {d.title}
              <span className="aic-doc-meta">{d.filename}</span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="aic-panel-section">
        <span className="aic-eyebrow">Depth</span>
        <div className="aic-modes" role="radiogroup" aria-label="Depth">
          {DEPTHS.map((d) => (
            <label key={d.value} className={`aic-mode${depth === d.value ? ' is-selected' : ''}`}>
              <span className="aic-mode-title">
                <input type="radio" name="aic-depth" value={d.value} checked={depth === d.value}
                       onChange={() => setDepth(d.value)} />
                {d.label}
              </span>
              <span className="aic-mode-hint">{d.hint}</span>
            </label>
          ))}
        </div>
      </div>
      {setups.length > 0 && (
        <div className="aic-panel-section">
          <label className="aic-eyebrow" htmlFor="aic-setup">Models</label>
          <select id="aic-setup" className="form-select form-select-sm" value={setup}
                  onChange={(e) => setSetup(e.target.value)}>
            {setups.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          {chosen && (depth === 'quick'
            ? <span className="aic-mode-hint">One call on {chosen.labels.quick}</span>
            : <span className="aic-mode-hint">{chosen.labels.gather} → {chosen.labels.extract} → {chosen.labels.analyze}</span>
          )}
        </div>
      )}
      <div className="aic-panel-footer">
        <span className="aic-muted">
          {depth === 'quick' ? 'One call · usually under a minute' : 'Gather → Extract → Analyze · usually 2–6 min'} · keeps running if you leave
        </span>
        <div className="aic-actions">
          <button type="button" className="btn btn-outline-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={!canRun || busy}
                  onClick={() => onRun(mode, needsDocs ? picked : [], setup, depth)}>Run AI check</button>
        </div>
      </div>
    </section>
  );
}
