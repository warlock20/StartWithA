/**
 * CompositionStrip — Thin horizontal stacked bar showing portfolio composition.
 *
 * Each segment is sized proportionally by current value.
 * Hover reveals a tooltip with ticker, weight %, and value.
 */
import { useState, useMemo } from 'react';
import { colors, fonts } from '../../tokens';
import { sectorColor, fmtCur } from './portfolioUtils';

export function CompositionStrip({
  positions,
  cashBalance,
  totalValue,
  showCash = true,
  height = 8,
  currencySymbol,
  sectorColorMap,
}) {
  const items = useMemo(() => {
    const sorted = [...positions].sort((a, b) => (b.current_value || 0) - (a.current_value || 0));
    const arr = sorted.map((p) => ({
      label: p.ticker,
      value: p.current_value || 0,
      pct: totalValue > 0 ? ((p.current_value || 0) / totalValue) * 100 : 0,
      color: sectorColor(p.sector, sectorColorMap),
    }));
    if (showCash && cashBalance > 0) {
      arr.push({
        label: 'Cash',
        value: cashBalance,
        pct: totalValue > 0 ? (cashBalance / totalValue) * 100 : 0,
        color: '#94a3b8',
      });
    }
    return arr;
  }, [positions, cashBalance, totalValue, showCash, sectorColorMap]);

  const [hover, setHover] = useState(null);

  return (
    <div style={{ position: 'relative' }}>
      <div
        style={{
          display: 'flex',
          height,
          borderRadius: height / 2,
          overflow: 'hidden',
          background: colors.gray100,
        }}
      >
        {items.map((it, i) => (
          <div
            key={it.label}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{
              width: it.pct + '%',
              minWidth: it.pct > 0.5 ? 2 : 0,
              background: it.color,
              opacity: hover != null && hover !== i ? 0.4 : 1,
              transition: 'opacity .15s',
              cursor: 'default',
            }}
          />
        ))}
      </div>
      {hover != null && items[hover] && (
        <div
          style={{
            position: 'absolute',
            top: height + 6,
            left: '50%',
            transform: 'translateX(-50%)',
            background: colors.gray800,
            color: colors.white,
            padding: '4px 10px',
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 600,
            fontFamily: fonts.mono,
            whiteSpace: 'nowrap',
            zIndex: 10,
            pointerEvents: 'none',
            boxShadow: '0 4px 12px rgba(0,0,0,.15)',
          }}
        >
          {items[hover].label} &middot; {items[hover].pct.toFixed(1)}% &middot;{' '}
          {fmtCur(items[hover].value, currencySymbol)}
        </div>
      )}
    </div>
  );
}
