/**
 * Portfolio Charts — DonutChart, PLBarChart, SectorLegend.
 *
 * All charts are pure SVG / CSS — no external chart library needed.
 */
import { useState, useMemo } from 'react';
import { colors, fonts } from '../../tokens';
import { sectorColor, fmtSign, plColor } from './portfolioUtils';

// ═══════════════════════════════════════════════════════════════════════════
// DONUT CHART (pure SVG)
// ═══════════════════════════════════════════════════════════════════════════
export function DonutChart({ data, size = 190, thickness = 34, centerLabel, centerValue }) {
  const [hoverIdx, setHoverIdx] = useState(null);
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transform: 'rotate(-90deg)' }}
      >
        {data.map((d, i) => {
          const pct = total > 0 ? d.value / total : 0;
          const dash = pct * circumference;
          const gap = circumference - dash;
          const segment = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={d.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={-offset}
              opacity={hoverIdx != null && hoverIdx !== i ? 0.3 : 1}
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
              style={{ transition: 'opacity .15s', cursor: 'default' }}
            />
          );
          offset += dash;
          return segment;
        })}
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'none',
        }}
      >
        {hoverIdx != null ? (
          <>
            <div style={{ fontSize: 13, fontWeight: 600, color: colors.gray500 }}>
              {data[hoverIdx].label}
            </div>
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: colors.gray800,
                fontFamily: fonts.mono,
              }}
            >
              {(total > 0 ? (data[hoverIdx].value / total) * 100 : 0).toFixed(1)}%
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 13, fontWeight: 600, color: colors.gray500 }}>
              {centerLabel}
            </div>
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: colors.gray800,
                fontFamily: fonts.mono,
              }}
            >
              {centerValue}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// P/L BAR CHART
// ═══════════════════════════════════════════════════════════════════════════
export function PLBarChart({ positions, sortBy, currencySymbol }) {
  const sorted = useMemo(() => {
    const arr = [...positions];
    if (sortBy === 'value') arr.sort((a, b) => (b.current_value || 0) - (a.current_value || 0));
    else if (sortBy === 'return')
      arr.sort((a, b) => (b.gain_loss_pct || 0) - (a.gain_loss_pct || 0));
    else if (sortBy === 'weight')
      arr.sort((a, b) => (b.weightPortfolio || 0) - (a.weightPortfolio || 0));
    else arr.sort((a, b) => Math.abs(b.gain_loss || 0) - Math.abs(a.gain_loss || 0));
    return arr;
  }, [positions, sortBy]);

  const maxAbs = Math.max(...sorted.map((p) => Math.abs(p.gain_loss || 0)), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {sorted.map((p) => {
        const pct = (Math.abs(p.gain_loss || 0) / maxAbs) * 100;
        const isGain = (p.gain_loss || 0) >= 0;
        return (
          <div
            key={p.company_id}
            style={{
              display: 'grid',
              gridTemplateColumns: '80px 1fr 90px',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: colors.textPrimary,
                textAlign: 'right',
              }}
            >
              {p.ticker}
            </div>
            <div
              style={{
                height: 18,
                background: colors.gray100,
                borderRadius: 4,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  borderRadius: 4,
                  width: pct + '%',
                  background: isGain ? '#d1fae5' : '#fee2e2',
                  border: `1px solid ${isGain ? '#a7f3d0' : '#fecaca'}`,
                  transition: 'width .3s ease',
                }}
              />
            </div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                fontFamily: fonts.mono,
                color: plColor(p.gain_loss),
                textAlign: 'right',
              }}
            >
              {fmtSign(p.gain_loss, currencySymbol)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SECTOR LEGEND
// ═══════════════════════════════════════════════════════════════════════════
export function SectorLegend({ sectors, showCount, sectorColorMap }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
      {sectors.map((s) => (
        <div
          key={s.name}
          style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13 }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: sectorColor(s.name, sectorColorMap),
              flexShrink: 0,
            }}
          />
          <span style={{ color: colors.textSecondary, fontWeight: 500 }}>{s.name}</span>
          {showCount && <span style={{ color: colors.gray400 }}>({s.count})</span>}
        </div>
      ))}
    </div>
  );
}

