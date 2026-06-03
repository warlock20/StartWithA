import { useMemo } from 'react';
import { calcMarginOfSafety } from '../../lib/intelligenceEngine';

/**
 * Margin of Safety calculator tab (Graham Formula).
 * Renders growth-rate slider, gauge bar, fair-value vs your-price, summary, and formula.
 */
export function MarginTab({ companyData, growthRate, onGrowthRateChange, price, currencySymbol }) {
  const eps = companyData?.eps_ttm;
  const ticker = companyData?.ticker;

  const result = useMemo(
    () => (eps && price ? calcMarginOfSafety(eps, growthRate, price) : null),
    [eps, growthRate, price],
  );

  // Gauge defaults
  let gaugeWidth = '50%';
  let gaugeColor = '#9ca3af';
  let fairValueText = '--';
  let yourPriceText = '--';

  if (result) {
    fairValueText = `${currencySymbol}${result.intrinsicValue.toFixed(2)}`;
    yourPriceText = `${currencySymbol}${result.currentPrice.toFixed(2)}`;
    gaugeWidth = `${Math.min(Math.max(50 + result.margin / 2, 2), 98)}%`;

    if (result.margin > 30) gaugeColor = '#2d6a4f';
    else if (result.margin > 15) gaugeColor = '#10b981';
    else if (result.margin > 0) gaugeColor = '#f59e0b';
    else if (result.margin > -15) gaugeColor = '#f97316';
    else gaugeColor = '#ef4444';
  }

  // Summary text
  let summaryContent = null;
  if (result) {
    const marginText = result.margin >= 0
      ? `+${result.margin.toFixed(1)}% margin`
      : `${result.margin.toFixed(1)}% premium`;

    const summaryColor = result.margin >= 30 ? '#2d6a4f'
      : result.margin >= 15 ? '#10b981'
      : result.margin >= 0 ? '#f59e0b'
      : '#ef4444';

    const explanation = result.margin >= 30
      ? 'Strong margin of safety. The stock appears significantly undervalued based on Graham\u2019s formula.'
      : result.margin >= 15
        ? 'Decent margin of safety. Some buffer exists between fair value and current price.'
        : result.margin >= 0
          ? 'Thin margin of safety. Limited downside protection at this price.'
          : 'Trading above estimated fair value. Consider whether growth assumptions justify the premium.';

    summaryContent = (
      <>
        <div className="calc-summary-value" style={{ color: summaryColor }}>{marginText}</div>
        <div className="calc-summary-label">{explanation}</div>
      </>
    );
  }

  return (
    <div className="calc-card" id="calc-margin">
      <div className="calc-body">
        {/* Growth Rate Slider */}
        <div className="calc-slider-row">
          <label className="calc-slider-label">
            Expected Growth Rate
            <span className="intel-tooltip-trigger">
              <i className="bi bi-info-circle" style={{ marginLeft: 4, fontSize: 12, color: '#9ca3af' }} />
              <span className="intel-tooltip">
                The annual rate you expect the company&rsquo;s earnings to grow.
                Higher growth increases the estimated fair value.
              </span>
            </span>
          </label>
          <span className="calc-slider-value">{growthRate}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="50"
          step="1"
          value={growthRate}
          className="calc-range"
          onChange={(e) => onGrowthRateChange(Number(e.target.value))}
        />
        <div className="calc-range-labels">
          <span>0%</span><span>25%</span><span>50%</span>
        </div>

        {(!eps || !price) ? (
          <div className="calc-summary">
            <div className="calc-empty">
              {!eps
                ? `EPS data unavailable for ${ticker}`
                : 'Enter a price to calculate margin of safety'}
            </div>
          </div>
        ) : (
          <>
            {/* Gauge */}
            <div className="mos-gauge" style={{ marginTop: '1rem' }}>
              <div className="mos-gauge-track">
                <div className="mos-gauge-fill" style={{ width: gaugeWidth, background: gaugeColor }} />
                <div className="mos-gauge-center-mark" />
              </div>
              <div className="mos-gauge-labels">
                <span>Overvalued</span><span>Fair Value</span><span>Undervalued</span>
              </div>
            </div>

            {/* Fair Value vs Your Price */}
            <div className="mos-values">
              <div className="mos-value-item">
                <div className="mos-value-label">
                  Est. Fair Value
                  <span className="intel-tooltip-trigger">
                    <i className="bi bi-info-circle" style={{ marginLeft: 3, fontSize: 11, color: '#9ca3af' }} />
                    <span className="intel-tooltip">
                      Benjamin Graham formula: EPS &times; (8.5 + 2g). A simplified intrinsic
                      value estimate based on current earnings and expected growth.
                    </span>
                  </span>
                </div>
                <div className="mos-value-number">{fairValueText}</div>
              </div>
              <span className="mos-value-vs">vs</span>
              <div className="mos-value-item">
                <div className="mos-value-label">Your Price</div>
                <div className="mos-value-number">{yourPriceText}</div>
              </div>
            </div>

            {/* Summary */}
            <div className="calc-summary">{summaryContent}</div>

            {/* Insight */}
            {result && (
              <div className="calc-insight">
                <i className="bi bi-lightbulb-fill" />
                <span>
                  Graham recommended buying only when margin of safety exceeds <strong>30%</strong>.
                </span>
              </div>
            )}
          </>
        )}

        {/* Formula reference (always shown) */}
        <div className="calc-formula">
          <div className="calc-formula-title">
            <i className="bi bi-calculator" /> How it&rsquo;s calculated
          </div>
          <div className="calc-formula-equation">V = EPS &times; (8.5 + 2g)</div>
          <div className="calc-formula-legend">
            <span><strong>V</strong> = Intrinsic value</span>
            <span><strong>EPS</strong> = Trailing 12-month earnings per share</span>
            <span><strong>8.5</strong> = P/E base for a no-growth company</span>
            <span><strong>g</strong> = Expected annual growth rate (%)</span>
          </div>
        </div>

        <div className="calc-disclaimer">
          <i className="bi bi-exclamation-triangle" />
          <span>
            This is a simplified estimate for educational purposes only. It does not account
            for interest rates, industry factors, or balance sheet quality. Do not use as sole
            basis for investment decisions.
          </span>
        </div>
      </div>
    </div>
  );
}
