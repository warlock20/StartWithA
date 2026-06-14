/**
 * Portfolio Dashboard — Data utilities and formatting helpers.
 *
 * Centralizes enrichment logic (weights, sectors, sorting)
 * and number formatting so every component stays consistent.
 */

// ── Sector color palette ────────────────────────────────────────────────────
// Hand-picked to remain legible on both white and light-gray backgrounds.
const SECTOR_PALETTE = [
  '#3b82f6', '#8b5cf6', '#f59e0b', '#06b6d4', '#10b981',
  '#ec4899', '#f97316', '#6366f1', '#14b8a6', '#e11d48',
  '#84cc16', '#a855f7', '#0ea5e9', '#d946ef', '#22c55e',
];
const CASH_COLOR = '#94a3b8';

/** Stable sector → color mapping (built once per render cycle). */
export function buildSectorColorMap(positions) {
  const seen = {};
  let idx = 0;
  positions.forEach((p) => {
    if (p.sector && !seen[p.sector]) {
      seen[p.sector] = SECTOR_PALETTE[idx % SECTOR_PALETTE.length];
      idx++;
    }
  });
  return seen;
}

export function sectorColor(name, colorMap) {
  if (name === 'Cash') return CASH_COLOR;
  return (colorMap && colorMap[name]) || '#6b7280';
}

// ── Enrichment ──────────────────────────────────────────────────────────────
/** Add weight fields to each position. Returns a new array. */
export function enrichPositions(positions, cashBalance) {
  const totalEquity = positions.reduce((s, p) => s + (p.current_value || 0), 0);
  const totalPortfolio = totalEquity + cashBalance;

  return positions.map((p) => ({
    ...p,
    cost_basis: p.cost_basis || (p.avg_cost && p.shares ? p.avg_cost * p.shares : 0),
    weightEquity: totalEquity > 0 ? ((p.current_value || 0) / totalEquity) * 100 : 0,
    weightPortfolio: totalPortfolio > 0 ? ((p.current_value || 0) / totalPortfolio) * 100 : 0,
  }));
}

/** Build sector aggregations from enriched positions. */
export function buildSectors(positions, totalPortfolioValue) {
  const map = {};
  positions.forEach((p) => {
    const s = p.sector || 'Uncategorized';
    if (!map[s]) map[s] = { name: s, value: 0, cost: 0, count: 0 };
    map[s].value += p.current_value || 0;
    map[s].cost += p.cost_basis || 0;
    map[s].count++;
  });
  return Object.values(map)
    .map((s) => ({
      ...s,
      weight: totalPortfolioValue > 0 ? (s.value / totalPortfolioValue) * 100 : 0,
      gainLoss: s.value - s.cost,
      gainLossPct: s.cost > 0 ? ((s.value - s.cost) / s.cost) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value);
}

// ── Formatting helpers ──────────────────────────────────────────────────────
export function fmt(n, decimals = 0) {
  if (n == null) return '--';
  return n.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtCur(n, currencySymbol, decimals = 0) {
  if (n == null) return '--';
  return currencySymbol + fmt(n, decimals);
}

export function fmtPct(n, decimals = 1) {
  if (n == null) return '--';
  return (n >= 0 ? '+' : '') + n.toFixed(decimals) + '%';
}

export function fmtSign(n, currencySymbol, decimals = 0) {
  if (n == null) return '--';
  return (n >= 0 ? '+' : '-') + currencySymbol + fmt(Math.abs(n), decimals);
}

// ── P/L color helpers ───────────────────────────────────────────────────────
export const plColor = (v) => (v >= 0 ? '#059669' : '#dc2626');
export const plBg = (v) => (v >= 0 ? '#ecfdf5' : '#fef2f2');

// ── Sorting ─────────────────────────────────────────────────────────────────
export function sortPositions(positions, sortKey) {
  const arr = [...positions];
  switch (sortKey) {
    case 'value':
      return arr.sort((a, b) => (b.current_value || 0) - (a.current_value || 0));
    case 'pl':
      return arr.sort((a, b) => (b.gain_loss || 0) - (a.gain_loss || 0));
    case 'return':
      return arr.sort((a, b) => (b.gain_loss_pct || 0) - (a.gain_loss_pct || 0));
    case 'weight':
      return arr.sort((a, b) => (b.weightPortfolio || 0) - (a.weightPortfolio || 0));
    case 'name':
      return arr.sort((a, b) => a.ticker.localeCompare(b.ticker));
    default:
      return arr;
  }
}
