/**
 * Intelligence Engine - Calculator Functions
 * Pure math functions for the Investment Intelligence Panel.
 * No DOM manipulation here - used by intelligence-panel.js.
 */
'use strict';

var IntelligenceEngine = (function() {

    /**
     * Earnings Payback Period Calculator
     * Given P/E and expected growth, when do cumulative earnings
     * equal the purchase price (normalized to 1x earnings)?
     *
     * @param {number} pe - Price-to-Earnings ratio
     * @param {number} growthRate - Expected annual growth rate (%)
     * @param {number} [maxYears=30] - Maximum years to calculate
     * @returns {Object|null} { labels, cumulativeData, paybackYear, pe }
     */
    function calcEarningsPayback(pe, growthRate, maxYears) {
        maxYears = maxYears || 30;
        if (!pe || pe <= 0) return null;

        var g = growthRate / 100;
        var labels = [];
        var cumulativeData = [];
        var runningTotal = 0;
        var paybackYear = null;

        for (var t = 0; t <= maxYears; t++) {
            labels.push(t);
            if (t > 0) runningTotal += Math.pow(1 + g, t);
            cumulativeData.push(runningTotal);
            if (paybackYear === null && runningTotal >= pe) paybackYear = t;
        }

        return {
            labels: labels,
            cumulativeData: cumulativeData,
            paybackYear: paybackYear,
            pe: pe
        };
    }

    /**
     * Required CAGR to achieve payback in N years (bisection method)
     *
     * @param {number} targetPE - Target P/E ratio to pay back
     * @param {number} n - Number of years for payback
     * @returns {number} Required CAGR in percentage
     */
    function findRequiredCAGR(targetPE, n) {
        var low = -0.99, high = 5.0, mid = 0;
        for (var i = 0; i < 100; i++) {
            mid = (low + high) / 2;
            var sum = mid === 0 ? n : ((1 + mid) * (Math.pow(1 + mid, n) - 1)) / mid;
            if (Math.abs(sum - targetPE) < 0.00001) break;
            if (sum < targetPE) low = mid; else high = mid;
        }
        return mid * 100;
    }

    /**
     * Margin of Safety (Graham Formula)
     * V = EPS x (8.5 + 2g) where g = expected growth %
     *
     * @param {number} eps - Earnings per share (TTM)
     * @param {number} growthRate - Expected annual growth rate (%)
     * @param {number} currentPrice - Current share price
     * @returns {Object|null} { intrinsicValue, currentPrice, margin }
     */
    function calcMarginOfSafety(eps, growthRate, currentPrice) {
        if (!eps || !currentPrice) return null;
        var intrinsicValue = eps * (8.5 + 2 * growthRate);
        var margin = ((intrinsicValue - currentPrice) / intrinsicValue) * 100;
        return {
            intrinsicValue: intrinsicValue,
            currentPrice: currentPrice,
            margin: margin
        };
    }

    /**
     * Break-even Calculator
     * Accounts for trading fees in cost basis
     *
     * @param {number} quantity - Number of shares
     * @param {number} pricePerShare - Price per share
     * @param {number} fees - Total trading fees
     * @returns {Object|null} { totalCost, breakEvenPrice, feesPerShare, quantity, pricePerShare, fees }
     */
    function calcBreakEven(quantity, pricePerShare, fees) {
        if (!quantity || !pricePerShare) return null;
        var f = fees || 0;
        var totalCost = quantity * pricePerShare + f;
        var breakEvenPrice = totalCost / quantity;
        var feesPerShare = f / quantity;
        return {
            totalCost: totalCost,
            breakEvenPrice: breakEvenPrice,
            feesPerShare: feesPerShare,
            quantity: quantity,
            pricePerShare: pricePerShare,
            fees: f
        };
    }

    // Public API
    return {
        calcEarningsPayback: calcEarningsPayback,
        findRequiredCAGR: findRequiredCAGR,
        calcMarginOfSafety: calcMarginOfSafety,
        calcBreakEven: calcBreakEven
    };
})();
