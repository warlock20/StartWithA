import { describe, it, expect } from 'vitest';
import { calcMarginOfSafety } from '../lib/intelligenceEngine';

describe('calcMarginOfSafety', () => {
  describe('negative earnings', () => {
    // Graham's formula divides by intrinsic value. With negative EPS that value
    // is negative, flipping the sign of the margin: a stock trading far above a
    // negative fair value was reported as deeply undervalued.
    it('reports loss-making companies as not applicable', () => {
      const eps = -97.50 / (8.5 + 2 * 15);  // yields a -$97.50 fair value at g=15
      const result = calcMarginOfSafety(eps, 15, 145.02);

      expect(result.notApplicable).toBe(true);
      expect(result.reason).toBe('negative_eps');
      expect(result.margin).toBeUndefined();
    });

    it('does not report a positive margin for an overvalued loss-maker', () => {
      const result = calcMarginOfSafety(-2.53, 15, 145.02);
      expect(result.margin).toBeUndefined();
      expect(result.intrinsicValue).toBeUndefined();
    });

    it('treats a small loss the same as a large one', () => {
      expect(calcMarginOfSafety(-0.01, 10, 50).notApplicable).toBe(true);
      expect(calcMarginOfSafety(-500, 10, 50).notApplicable).toBe(true);
    });
  });

  describe('profitable companies', () => {
    it('computes fair value from EPS and growth', () => {
      const result = calcMarginOfSafety(10, 15, 100);
      expect(result.intrinsicValue).toBe(385);       // 10 x (8.5 + 30)
      expect(result.currentPrice).toBe(100);
    });

    it('reports a positive margin when trading below fair value', () => {
      const result = calcMarginOfSafety(10, 15, 100);
      expect(result.margin).toBeCloseTo(74.03, 1);
    });

    it('reports a negative margin when trading above fair value', () => {
      const result = calcMarginOfSafety(2, 5, 100);   // fair value 37
      expect(result.intrinsicValue).toBe(37);
      expect(result.margin).toBeLessThan(0);
    });

    it('reports roughly zero margin at fair value', () => {
      const result = calcMarginOfSafety(10, 15, 385);
      expect(result.margin).toBeCloseTo(0, 5);
    });

    it('raises fair value as the growth assumption rises', () => {
      const low = calcMarginOfSafety(5, 0, 100);
      const high = calcMarginOfSafety(5, 30, 100);
      expect(high.intrinsicValue).toBeGreaterThan(low.intrinsicValue);
    });
  });

  describe('missing inputs', () => {
    it('returns null without EPS', () => {
      expect(calcMarginOfSafety(null, 15, 100)).toBeNull();
      expect(calcMarginOfSafety(undefined, 15, 100)).toBeNull();
      expect(calcMarginOfSafety(0, 15, 100)).toBeNull();
    });

    it('returns null without a price', () => {
      expect(calcMarginOfSafety(5, 15, 0)).toBeNull();
      expect(calcMarginOfSafety(5, 15, null)).toBeNull();
    });
  });
});
