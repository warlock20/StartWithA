import { mountIsland } from './lib/mountIsland';
import { MarketSweep } from './components/market-sweep/MarketSweep';

/**
 * Market Sweep — React island entry.
 *
 * Exposes `window.initMarketSweep(elementId, config)` for template initialization.
 * Config: { sectors: Array<{ id, name }> }
 */
window.initMarketSweep = function (elementId, config) {
  return mountIsland(elementId, MarketSweep, config);
};
