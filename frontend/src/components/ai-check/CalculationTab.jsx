import { useId, useState } from 'react';
import { groupCalculation } from './resultView';

function CalcRows({ lines, activeLabel, onShowEvidence }) {
  return (
    <table className="aic-table aic-calc">
      <tbody>
        {lines.map((line, i) => (
          <tr key={i} className={`is-${line.kind}`}>
            <td>{line.label}{line.note && <div className="aic-note">{line.note}</div>}</td>
            <td className="aic-num aic-mono">{line.value}</td>
            <td className="aic-refs">
              {(line.evidence || []).map((label) => (
                <button key={label} type="button" className={`aic-ref${label === activeLabel ? ' is-active' : ''}`}
                        onClick={() => onShowEvidence(label)}>{label}</button>
              ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CalculationTab({ calculation, activeLabel, onShowEvidence }) {
  const groups = groupCalculation(calculation);
  const [open, setOpen] = useState(() => new Set([0]));
  const baseId = useId();

  if (!groups.length) return <p className="aic-muted">No calculation lines.</p>;
  if (groups.length === 1 && groups[0].name === null) {
    return <CalcRows lines={groups[0].lines} activeLabel={activeLabel} onShowEvidence={onShowEvidence} />;
  }
  const toggle = (index) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(index)) next.delete(index); else next.add(index);
    return next;
  });
  return (
    <div className="aic-groups">
      <p className="aic-muted">Open a section to see its lines. Click a figure to see its source.</p>
      {groups.map((group, index) => {
        const isOpen = open.has(index);
        const panelId = `${baseId}-group-${index}`;
        return (
          <div key={group.name || `other-${index}`} className="aic-group">
            <button type="button" className="aic-group-head" aria-expanded={isOpen} aria-controls={panelId}
                    onClick={() => toggle(index)}>
              <i className={`bi bi-chevron-right aic-chevron${isOpen ? ' is-open' : ''}`} aria-hidden="true" />
              <span className="aic-group-name">{group.name || 'Other'}</span>
              <span className="aic-group-label">{group.total ? group.total.label : ''}</span>
              <span className="aic-mono aic-strong">{group.total ? group.total.value : ''}</span>
              <span className="aic-group-count">{group.lines.length} lines</span>
            </button>
            {isOpen && (
              <div id={panelId} className="aic-group-body">
                <CalcRows lines={group.lines} activeLabel={activeLabel} onShowEvidence={onShowEvidence} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
