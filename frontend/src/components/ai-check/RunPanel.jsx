import { useState } from 'react';

const MODES = [
  { value: 'documents', label: 'My documents', hint: 'Only the files you tick. No web. Page references.' },
  { value: 'web', label: 'Web research', hint: 'Claude finds and reads filings itself.' },
  { value: 'both', label: 'Both', hint: 'Your documents first; web only for gaps.' },
];

export function RunPanel({ documents, onRun, onCancel }) {
  const [mode, setMode] = useState(documents.length ? 'both' : 'web');
  const [picked, setPicked] = useState(documents.length ? [documents[0].id] : []);
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
      <div className="aic-panel-footer">
        <span className="aic-muted">Gather → Extract → Analyze · usually 2–6 min · keeps running if you leave</span>
        <div className="aic-actions">
          <button type="button" className="btn btn-outline-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={!canRun}
                  onClick={() => onRun(mode, needsDocs ? picked : [])}>Run AI check</button>
        </div>
      </div>
    </section>
  );
}
