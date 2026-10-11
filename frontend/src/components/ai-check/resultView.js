/** Pure view helpers for the AI check result card. Fields may be missing on runs saved before v2. */

const MAX_FIGURES = 3;

export function groupCalculation(lines) {
  const list = lines || [];
  if (!list.some((line) => line.group)) return list.length ? [{ name: null, lines: list, total: null }] : [];
  const groups = new Map();
  const ungrouped = [];
  list.forEach((line) => {
    if (!line.group) { ungrouped.push(line); return; }
    if (!groups.has(line.group)) groups.set(line.group, { name: line.group, lines: [], total: null });
    const group = groups.get(line.group);
    group.lines.push(line);
    if (line.kind === 'total') group.total = line;
  });
  const result = [...groups.values()];
  if (ungrouped.length) result.push({ name: null, lines: ungrouped, total: null });
  return result;
}

export function keyFigures(result) {
  const r = result || {};
  if (r.key_figures && r.key_figures.length) return r.key_figures.slice(0, MAX_FIGURES);
  return (r.calculation || [])
    .filter((line) => line.kind === 'total')
    .slice(0, MAX_FIGURES)
    .map((line) => ({
      label: line.group ? `${line.group} · ${line.label}` : line.label,
      value: line.value,
      evidence: line.evidence || [],
    }));
}

export function filterEvidence(evidence, { query = '', unverifiedOnly = false } = {}) {
  const q = query.trim().toLowerCase();
  return (evidence || []).filter((e) => {
    if (unverifiedOnly && e.verified) return false;
    if (!q) return true;
    return [e.label, e.metric, e.period, e.quote].some((field) => (field || '').toLowerCase().includes(q));
  });
}

export function usedIn(label, calculation) {
  const names = (calculation || [])
    .filter((line) => (line.evidence || []).includes(label))
    .map((line) => (line.group ? `${line.group} · ${line.label}` : line.label));
  return [...new Set(names)];
}

export function defaultTab(result) {
  return result && (result.calculation || []).length ? 'calculation' : 'summary';
}

export function isLongText(text, limit = 320) {
  return (text || '').length > limit;
}
