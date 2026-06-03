/**
 * Intelligence Engine — pure math functions for the Investment Intelligence Panel.
 * ES module version of intelligence-engine.js. No DOM manipulation.
 */

/**
 * Earnings Payback Period: when cumulative earnings equal purchase price.
 * @param {number} pe  Price-to-Earnings ratio
 * @param {number} growthRate  Expected annual growth (%)
 * @param {number} [maxYears=30]
 * @returns {{ labels: number[], cumulativeData: number[], paybackYear: number|null, pe: number } | null}
 */
export function calcEarningsPayback(pe, growthRate, maxYears = 30) {
  if (!pe || pe <= 0) return null;

  const g = growthRate / 100;
  const labels = [];
  const cumulativeData = [];
  let runningTotal = 0;
  let paybackYear = null;

  for (let t = 0; t <= maxYears; t++) {
    labels.push(t);
    if (t > 0) runningTotal += Math.pow(1 + g, t);
    cumulativeData.push(runningTotal);
    if (paybackYear === null && runningTotal >= pe) paybackYear = t;
  }

  return { labels, cumulativeData, paybackYear, pe };
}

/**
 * Required CAGR to achieve payback in N years (bisection method).
 * @param {number} targetPE  Target P/E to pay back
 * @param {number} n  Number of years
 * @returns {number}  Required CAGR in percentage
 */
export function findRequiredCAGR(targetPE, n) {
  let low = -0.99;
  let high = 5.0;
  let mid = 0;
  for (let i = 0; i < 100; i++) {
    mid = (low + high) / 2;
    const sum = mid === 0 ? n : ((1 + mid) * (Math.pow(1 + mid, n) - 1)) / mid;
    if (Math.abs(sum - targetPE) < 0.00001) break;
    if (sum < targetPE) low = mid;
    else high = mid;
  }
  return mid * 100;
}

/**
 * Margin of Safety via Graham Formula: V = EPS x (8.5 + 2g).
 * @param {number} eps  Trailing 12-month EPS
 * @param {number} growthRate  Expected annual growth (%)
 * @param {number} currentPrice  Current share price
 * @returns {{ intrinsicValue: number, currentPrice: number, margin: number } | null}
 */
export function calcMarginOfSafety(eps, growthRate, currentPrice) {
  if (!eps || !currentPrice) return null;
  const intrinsicValue = eps * (8.5 + 2 * growthRate);
  const margin = ((intrinsicValue - currentPrice) / intrinsicValue) * 100;
  return { intrinsicValue, currentPrice, margin };
}

/**
 * Break-even Calculator — accounts for trading fees.
 * @param {number} quantity  Number of shares
 * @param {number} pricePerShare  Price per share
 * @param {number} [fees=0]  Total trading fees
 * @returns {{ totalCost: number, breakEvenPrice: number, feesPerShare: number, quantity: number, pricePerShare: number, fees: number } | null}
 */
export function calcBreakEven(quantity, pricePerShare, fees = 0) {
  if (!quantity || !pricePerShare) return null;
  const totalCost = quantity * pricePerShare + fees;
  return {
    totalCost,
    breakEvenPrice: totalCost / quantity,
    feesPerShare: fees / quantity,
    quantity,
    pricePerShare,
    fees,
  };
}
