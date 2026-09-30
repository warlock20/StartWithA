import { useCallback, useEffect, useRef, useState } from 'react';
import { apiGet, apiPost } from '../../lib/api';
import { RunPanel } from './RunPanel';
import { RunProgress } from './RunProgress';
import { ResultCard } from './ResultCard';
import { TERMINAL } from './progress';

const POLL_MS = 3000;
const base = '/research/workflow';

/**
 * AI check island for one checklist question on the research step.
 * Views: closed (button) → panel (pick sources) → running (tracker) → result / failed.
 */
export function AICheck({ config }) {
  const [itemId, setItemId] = useState(config.itemId);
  const [hasAiContext, setHasAiContext] = useState(config.hasAiContext);
  const [panelOpen, setPanelOpen] = useState(false);
  const [run, setRun] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const itemRef = useRef(itemId);

  const itemUrl = (id) => `${base}/checklist/${config.analysisId}/item/${id}/ai_check`;

  const loadHistory = useCallback(async (id) => {
    const data = await apiGet(`${itemUrl(id)}/history`);
    if (itemRef.current !== id) return; // navigated away meanwhile
    setHistory(data.runs || []);
    setRun(data.latest || null);
  }, [config.analysisId]);

  useEffect(() => {
    window.aiCheck = {
      updateContext: ({ itemId: nextId, hasAiContext: nextHas }) => {
        itemRef.current = nextId;
        setItemId(nextId);
        setHasAiContext(!!nextHas);
        setPanelOpen(false);
        setRun(null);
        setHistory([]);
        setError(null);
      },
    };
    return () => { delete window.aiCheck; };
  }, []);

  useEffect(() => {
    if (hasAiContext) loadHistory(itemId).catch(() => {});
  }, [itemId, hasAiContext, loadHistory]);

  // Poll the current run until it reaches a terminal status. Keyed on run id + item,
  // so switching items (run reset to null) clears the interval.
  const runId = run && run.id;
  const runActive = run && !TERMINAL.includes(run.status);
  useEffect(() => {
    if (!runActive) return undefined;
    const pollItem = itemId;
    const timer = setInterval(async () => {
      try {
        const data = await apiGet(`${base}/ai_check/${runId}`);
        if (itemRef.current === pollItem) setRun(data.run);
      } catch (e) { /* keep polling; the reaper ends stuck runs */ }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [runId, runActive, itemId]);

  if (!hasAiContext) return null;

  const errorText = (e) => (e.data && (e.data.message || e.data.error)) || e.message;

  const start = async (mode, documentIds) => {
    const forItem = itemId;
    setError(null);
    try {
      const data = await apiPost(itemUrl(forItem), { mode, document_ids: documentIds });
      if (itemRef.current !== forItem) return; // navigated away meanwhile
      setRun(data.run);
      setPanelOpen(false);
    } catch (e) {
      if (itemRef.current === forItem) setError(errorText(e));
    }
  };
  const act = async (verb) => {
    const forItem = itemId;
    try {
      const data = await apiPost(`${base}/ai_check/${run.id}/${verb}`, {});
      if (itemRef.current !== forItem) return;
      setError(null);
      setRun(data.run);
    } catch (e) {
      if (itemRef.current === forItem) setError(errorText(e));
    }
  };

  return (
    <div className="aic">
      <div className="aic-toolbar">
        <button type="button" className="btn btn-primary btn-sm"
                onClick={() => setPanelOpen((open) => !open)} disabled={runActive}>
          <i className="bi bi-stars" aria-hidden="true" /> AI check
        </button>
      </div>
      {error && <div className="aic-alert" role="alert">{error}</div>}
      {panelOpen && !runActive && (
        <RunPanel documents={config.documents} onRun={start} onCancel={() => setPanelOpen(false)} />
      )}
      {run && !TERMINAL.includes(run.status) && <RunProgress run={run} onCancel={() => act('cancel')} />}
      {run && TERMINAL.includes(run.status) && (
        <ResultCard run={run} history={history} onRetry={() => act('retry')}
                    onRerun={() => setPanelOpen(true)} />
      )}
    </div>
  );
}
