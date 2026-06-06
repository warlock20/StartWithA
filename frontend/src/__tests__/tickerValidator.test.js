import { describe, it, expect } from 'vitest';
import { TickerValidator } from '../lib/tickerValidator';

describe('TickerValidator', () => {
  describe('parseAndValidate', () => {
    it('validates simple US tickers', () => {
      const result = TickerValidator.parseAndValidate('AAPL');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('AAPL');
      expect(result.exchangeName).toBe('United States');
    });

    it('handles lowercase input', () => {
      const result = TickerValidator.parseAndValidate('msft');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('MSFT');
    });

    it('validates Yahoo format with exchange suffix', () => {
      const result = TickerValidator.parseAndValidate('SAP.DE');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('SAP.DE');
      expect(result.exchangeCode).toBe('.DE');
      expect(result.exchangeName).toBe('Germany (XETRA)');
    });

    it('validates Google Finance format', () => {
      const result = TickerValidator.parseAndValidate('FRA:SAP');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('SAP.F');
      expect(result.originalFormat).toBe('google');
    });

    it('converts share class dot to hyphen for US stocks', () => {
      const result = TickerValidator.parseAndValidate('BRK.B');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('BRK-B');
    });

    it('rejects empty ticker', () => {
      const result = TickerValidator.parseAndValidate('');
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Ticker symbol is required');
    });

    it('rejects null ticker', () => {
      const result = TickerValidator.parseAndValidate(null);
      expect(result.isValid).toBe(false);
    });

    it('rejects ticker that is too long', () => {
      const result = TickerValidator.parseAndValidate('A'.repeat(21));
      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toMatch(/too long/i);
    });

    it('rejects unknown Google exchange prefix', () => {
      const result = TickerValidator.parseAndValidate('FAKE:AAPL');
      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toMatch(/Unknown exchange/);
    });

    it('rejects unknown Yahoo exchange suffix', () => {
      const result = TickerValidator.parseAndValidate('AAPL.ZZ');
      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toMatch(/Unknown exchange suffix/);
    });

    it('warns about single-character tickers', () => {
      const result = TickerValidator.parseAndValidate('A');
      expect(result.isValid).toBe(true);
      expect(result.warnings).toContain('Single-character tickers are rare');
    });

    it('warns about long US tickers', () => {
      const result = TickerValidator.parseAndValidate('ABCDEF');
      expect(result.isValid).toBe(true);
      expect(result.warnings).toContain('Long US ticker symbols are uncommon');
    });

    it('rejects tickers starting with hyphen', () => {
      const result = TickerValidator.parseAndValidate('-AAPL');
      expect(result.isValid).toBe(false);
    });

    it('validates international tickers', () => {
      // Note: single-char suffixes like .L and .T are ambiguous with US share classes
      // (e.g., BRK.B). The validator prioritizes share class detection for [A-Z]{1,5}.[A-Z].
      // Use tickers with 2+ char suffixes or Google format for unambiguous testing.
      const tickers = [
        { input: 'LON:VOD', exchange: '.L', name: 'United Kingdom (LSE)' },
        { input: 'TTE.PA', exchange: '.PA', name: 'France (Euronext Paris)' },
        { input: '7203.T', exchange: '.T', name: 'Japan (Tokyo)' },
        { input: 'RY.TO', exchange: '.TO', name: 'Canada (Toronto)' },
      ];

      for (const t of tickers) {
        const result = TickerValidator.parseAndValidate(t.input);
        expect(result.isValid).toBe(true);
        expect(result.exchangeCode).toBe(t.exchange);
        expect(result.exchangeName).toBe(t.name);
      }
    });
  });

  describe('getBaseTicker', () => {
    it('removes exchange suffix', () => {
      expect(TickerValidator.getBaseTicker('SAP.DE')).toBe('SAP');
    });

    it('removes share class hyphen', () => {
      expect(TickerValidator.getBaseTicker('BRK-B')).toBe('BRK');
    });

    it('returns plain ticker as-is', () => {
      expect(TickerValidator.getBaseTicker('AAPL')).toBe('AAPL');
    });
  });

  describe('validate (quick helper)', () => {
    it('returns simplified result for valid ticker', () => {
      const result = TickerValidator.validate('AAPL');
      expect(result.isValid).toBe(true);
      expect(result.normalizedTicker).toBe('AAPL');
      expect(result.error).toBeNull();
    });

    it('returns error string for invalid ticker', () => {
      const result = TickerValidator.validate('');
      expect(result.isValid).toBe(false);
      expect(result.error).toBeTruthy();
    });
  });

  describe('formatForDisplay', () => {
    it('includes exchange name for international tickers', () => {
      const display = TickerValidator.formatForDisplay('SAP.DE', true);
      expect(display).toBe('SAP.DE (Germany (XETRA))');
    });

    it('omits exchange name for US tickers', () => {
      const display = TickerValidator.formatForDisplay('AAPL', true);
      expect(display).toBe('AAPL');
    });

    it('returns raw ticker for invalid input', () => {
      const display = TickerValidator.formatForDisplay('');
      expect(display).toBe('');
    });
  });
});
