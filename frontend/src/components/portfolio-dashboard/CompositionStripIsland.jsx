/**
 * CompositionStripIsland — Thin wrapper that mounts the composition strip
 * inside the Jinja header card with its own data enrichment.
 */
import { useMemo } from 'react';
import { CompositionStrip } from './CompositionStrip';
import { enrichPositions, buildSectorColorMap } from './portfolioUtils';

export function CompositionStripIsland({ holdings, portfolioValue, currencySymbol }) {
  const cashBalance = portfolioValue.cash_balance || 0;

  const enriched = useMemo(
    () => enrichPositions(holdings, cashBalance),
    [holdings, cashBalance]
  );

  const sectorColorMap = useMemo(() => buildSectorColorMap(enriched), [enriched]);

  return (
    <CompositionStrip
      positions={enriched}
      cashBalance={cashBalance}
      totalValue={portfolioValue.total_value}
      showCash
      height={8}
      currencySymbol={currencySymbol}
      sectorColorMap={sectorColorMap}
    />
  );
}
