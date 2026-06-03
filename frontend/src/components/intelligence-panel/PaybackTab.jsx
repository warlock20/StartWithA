import { useMemo } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { calcEarningsPayback, findRequiredCAGR } from '../../lib/intelligenceEngine';

/**
 * Earnings Payback Period calculator tab.
 * Renders growth-rate slider, Recharts line chart, summary, and insight.
 */
export function PaybackTab({ companyData, growthRate, onGrowthRateChange }) {
  const pe = companyData?.pe_ratio;
  const ticker = companyData?.ticker;

  const result = useMemo(
    () => (pe && pe > 0 ? calcEarningsPayback(pe, growthRate) : null),
    [pe, growthRate],
  );

  const reqCAGR = useMemo(
    () => (pe && pe > 0 ? findRequiredCAGR(pe, 10) : null),
    [pe],
  );

  const chartData = useMemo(() => {
    if (!result) return [];
    return result.labels.map((year, i) => ({
      label: year === 0 ? 'Now' : year % 5 === 0 ? `Yr ${year}` : '',
      year,
      cumulative: result.cumulativeData[i],
      pe: result.pe,
    }));
  }, [result]);

  // Payback colour coding
  let paybackColor = '#ef4444';
  if (result?.paybackYear) {
    if (result.paybackYear <= 10) paybackColor = '#2d6a4f';
    else if (result.paybackYear <= 20) paybackColor = '#d97706';
  }

  return (
    <div className="calc-card" id="calc-payback">
      <div className="calc-body">
        {/* Growth Rate Slider */}
        <div className="calc-slider-row">
          <label className="calc-slider-label">
            Expected Growth Rate
            <span className="intel-tooltip-trigger">
              <i className="bi bi-info-circle" style={{ marginLeft: 4, fontSize: 12, color: '#9ca3af' }} />
              <span className="intel-tooltip">
                The annual rate you expect the company&rsquo;s earnings to grow.
                Higher growth = faster payback.
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

        {/* Empty states when PE is unavailable */}
        {(!pe || pe <= 0) ? (
          <div className="calc-summary">
            <div className="calc-empty">
              {pe && pe < 0
                ? 'Negative P/E \u2014 company is not currently profitable. Earnings payback not applicable.'
                : `P/E data unavailable for ${ticker}`}
            </div>
          </div>
        ) : (
          <>
            {/* Recharts line chart */}
            <div style={{ height: 180, marginTop: 12 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}>
                  <defs>
                    <linearGradient id="paybackGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(45,106,79,0.22)" />
                      <stop offset="100%" stopColor="rgba(45,106,79,0.01)" />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: 'none',
                      borderRadius: 6,
                      padding: 8,
                      fontSize: 11,
                      color: '#fff',
                    }}
                    labelFormatter={(_, payload) => {
                      if (!payload?.[0]) return '';
                      const yr = payload[0].payload.year;
                      return yr === 0 ? 'Now' : `Year ${yr}`;
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="cumulative"
                    stroke="#2d6a4f"
                    fill="url(#paybackGrad)"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4 }}
                    name="Cumulative Earnings"
                  />
                  <Line
                    type="monotone"
                    dataKey="pe"
                    stroke="#ef4444"
                    strokeDasharray="6 4"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={false}
                    name="Purchase Price (P/E)"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <div className="calc-legend">
              <span>
                <span className="legend-dot" style={{ background: '#2d6a4f' }} />
                Cumulative Earnings
              </span>
              <span>
                <span className="legend-dot legend-dot--dashed" />
                Purchase Price
              </span>
            </div>

            {/* Summary */}
            <div className="calc-summary">
              <div className="calc-summary-value" style={{ color: paybackColor }}>
                {result.paybackYear ? `${result.paybackYear} years` : '30+ years'}
              </div>
              <div className="calc-summary-label">
                {result.paybackYear
                  ? `At ${growthRate}% annual growth, cumulative earnings cover the price in ${result.paybackYear} years.`
                  : `At ${growthRate}% growth, earnings won\u2019t cover the price within 30 years. Consider whether P/E of ${pe.toFixed(1)}\u00d7 is justified.`}
              </div>
            </div>

            {/* Insight */}
            {reqCAGR !== null && (
              <div className="calc-insight">
                <i className="bi bi-lightbulb-fill" />
                <span>
                  For a 10-year payback, this company needs{' '}
                  <strong>{reqCAGR.toFixed(1)}%</strong> annual earnings growth.
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
