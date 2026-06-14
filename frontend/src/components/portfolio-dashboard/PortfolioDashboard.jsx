/**
 * PortfolioDashboard — Main React island for the redesigned portfolio page.
 *
 * Renders below the Jinja header card. Provides:
 *  - Two-column layout: tabbed table (left) + charts sidebar (right)
 *  - Three table views: Overview / Weights / Performance
 *  - Two chart cards: Allocation (Sectors/Holdings), P/L
 *
 * The composition strip is mounted separately inside the header card.
 */
import { useState, useMemo } from 'react';
import { colors } from '../../tokens';
import { SegmentedControl } from '../shared/SegmentedControl';
import { DataTable } from '../shared/DataTable';
import { DonutChart, PLBarChart, SectorLegend } from './ChartComponents';
import {
  enrichPositions,
  buildSectors,
  buildSectorColorMap,
} from './portfolioUtils';
import { overviewColumns, weightsColumns, performanceColumns } from './portfolioColumnDefs';

export function PortfolioDashboard({
  holdings,
  portfolioValue,
  currencySymbol,
}) {
  // ── State ─────────────────────────────────────────────────────────────
  const [view, setView] = useState('overview');
  const [chartType, setChartType] = useState('donut-sector');
  const [plFilter, setPlFilter] = useState('all');
  const [search, setSearch] = useState('');

  const showCash = true;
  const cashBalance = portfolioValue.cash_balance || 0;

  // ── Enrichment ────────────────────────────────────────────────────────
  const enriched = useMemo(
    () => enrichPositions(holdings, cashBalance),
    [holdings, cashBalance]
  );

  const sectorColorMap = useMemo(() => buildSectorColorMap(enriched), [enriched]);

  const sectors = useMemo(
    () => buildSectors(enriched, portfolioValue.total_value),
    [enriched, portfolioValue.total_value]
  );

  const cashWeight = useMemo(
    () =>
      portfolioValue.total_value > 0
        ? (cashBalance / portfolioValue.total_value) * 100
        : 0,
    [cashBalance, portfolioValue.total_value]
  );

  // ── Filter (sorting handled by Tabulator) ────────────────────────────
  const filtered = useMemo(() => {
    let list = [...enriched];
    if (search.trim()) {
      const s = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.ticker.toLowerCase().includes(s) ||
          p.name.toLowerCase().includes(s) ||
          (p.sector && p.sector.toLowerCase().includes(s))
      );
    }
    if (plFilter === 'gains') list = list.filter((p) => (p.gain_loss || 0) >= 0);
    if (plFilter === 'losses') list = list.filter((p) => (p.gain_loss || 0) < 0);
    return list;
  }, [enriched, search, plFilter]);

  // ── Weights table data (append cash row) ────────────────────────────
  const weightsData = useMemo(() => {
    const data = [...filtered];
    if (cashBalance > 0) {
      data.push({
        _isCash: true,
        company_id: '__cash__',
        ticker: 'Cash',
        name: '',
        sector: null,
        current_value: cashBalance,
        weightPortfolio: cashWeight,
        weightEquity: null,
        position_url: '',
        add_tx_url: '',
      });
    }
    return data;
  }, [filtered, cashBalance, cashWeight]);

  // ── Tabulator column definitions (memoized) ─────────────────────────
  const overviewCols = useMemo(() => overviewColumns(currencySymbol), [currencySymbol]);
  const weightsCols = useMemo(() => weightsColumns(currencySymbol, sectorColorMap), [currencySymbol, sectorColorMap]);
  const performanceCols = useMemo(() => performanceColumns(currencySymbol), [currencySymbol]);

  const tableConfig = useMemo(() => ({
    pagination: false,
    layout: 'fitColumns',
    initialSort: [{ column: 'current_value', dir: 'desc' }],
    placeholder: 'No positions match your filters',
  }), []);

  const weightsRowFormatter = useMemo(() => {
    return function (row) {
      const data = row.getData();
      if (data._isCash) {
        row.getElement().style.backgroundColor = 'var(--gray-50, #f7f8fc)';
      }
    };
  }, []);

  // ── Chart data ────────────────────────────────────────────────────────
  const donutSectorData = useMemo(() => {
    const arr = sectors.map((s) => ({
      label: s.name,
      value: s.value,
      color: sectorColorMap[s.name] || '#6b7280',
    }));
    if (showCash && cashBalance > 0) {
      arr.push({ label: 'Cash', value: cashBalance, color: '#94a3b8' });
    }
    return arr;
  }, [sectors, cashBalance, sectorColorMap]);

  const donutPositionData = useMemo(() => {
    const sorted = [...enriched].sort(
      (a, b) => (b.current_value || 0) - (a.current_value || 0)
    );
    const arr = sorted.map((p) => ({
      label: p.ticker,
      value: p.current_value || 0,
      color: sectorColorMap[p.sector] || '#6b7280',
    }));
    if (showCash && cashBalance > 0) {
      arr.push({ label: 'Cash', value: cashBalance, color: '#94a3b8' });
    }
    return arr;
  }, [enriched, cashBalance, sectorColorMap]);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Two-column layout */}
      <div className="portfolio-redesign-grid">
        {/* LEFT: Table Panel */}
        <div className="rcl-panel" style={{ overflow: 'hidden' }}>
          {/* Tab bar + controls */}
          <div className="portfolio-table-controls">
            <div style={{ display: 'flex', gap: 4 }}>
              <TabBtn
                active={view === 'overview'}
                icon="table"
                onClick={() => setView('overview')}
              >
                Overview
              </TabBtn>
              <TabBtn
                active={view === 'weights'}
                icon="pie-chart"
                onClick={() => setView('weights')}
              >
                Weights
              </TabBtn>
              <TabBtn
                active={view === 'performance'}
                icon="graph-up"
                onClick={() => setView('performance')}
              >
                Performance
              </TabBtn>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 4 }}>
                <PlFilterChip active={plFilter === 'all'} onClick={() => setPlFilter('all')}>
                  All
                </PlFilterChip>
                <PlFilterChip active={plFilter === 'gains'} onClick={() => setPlFilter('gains')}>
                  Gains
                </PlFilterChip>
                <PlFilterChip active={plFilter === 'losses'} onClick={() => setPlFilter('losses')}>
                  Losses
                </PlFilterChip>
              </div>
              <div className="rcl-search" style={{ minWidth: 200 }}>
                <i className="bi bi-search" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search ticker or company..."
                />
              </div>
            </div>
          </div>

          {/* Table view (Tabulator) */}
          {view === 'overview' && (
            <DataTable
              columns={overviewCols}
              data={filtered}
              customConfig={tableConfig}
            />
          )}
          {view === 'weights' && (
            <DataTable
              columns={weightsCols}
              data={weightsData}
              customConfig={tableConfig}
              rowFormatter={weightsRowFormatter}
            />
          )}
          {view === 'performance' && (
            <DataTable
              columns={performanceCols}
              data={filtered}
              customConfig={tableConfig}
            />
          )}

          {/* Footer */}
          <div className="portfolio-table-footer">
            <span>
              {filtered.length} of {enriched.length} positions
            </span>
          </div>
        </div>

        {/* RIGHT: Charts Sidebar */}
        <div className="portfolio-charts-sidebar">
          {/* Allocation Chart */}
          <div className="rcl-panel" style={{ padding: 20 }}>
            <div className="portfolio-chart-title">
              <i className="bi bi-pie-chart-fill" style={{ color: colors.accent, fontSize: 15 }} />
              Allocation
            </div>
            <div style={{ marginBottom: 10 }}>
              <SegmentedControl
                options={[
                  { id: 'donut-sector', label: 'Sectors' },
                  { id: 'donut-position', label: 'Holdings' },
                ]}
                value={chartType}
                onChange={setChartType}
                stretch
              />
            </div>
            {chartType === 'donut-sector' && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
                <DonutChart
                  data={donutSectorData}
                  size={190}
                  thickness={34}
                  centerLabel="Sectors"
                  centerValue={sectors.length}
                />
                <SectorLegend sectors={sectors} showCount sectorColorMap={sectorColorMap} />
              </div>
            )}
            {chartType === 'donut-position' && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
                <DonutChart
                  data={donutPositionData}
                  size={190}
                  thickness={34}
                  centerLabel="Holdings"
                  centerValue={enriched.length}
                />
                <SectorLegend sectors={sectors} sectorColorMap={sectorColorMap} />
              </div>
            )}
          </div>

          {/* P/L Chart */}
          <div className="rcl-panel" style={{ padding: 20 }}>
            <div className="portfolio-chart-title">
              <i className="bi bi-bar-chart-fill" style={{ color: '#3b82f6', fontSize: 15 }} />
              Profit / Loss
            </div>
            <PLBarChart
              positions={enriched}
              sortBy="pl"
              currencySymbol={currencySymbol}
            />
          </div>

        </div>
      </div>
    </div>
  );
}

// ── Small UI helpers (local to this component) ──────────────────────────
function TabBtn({ active, icon, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`portfolio-tab-btn${active ? ' active' : ''}`}
    >
      {icon && <i className={`bi bi-${icon}`} style={{ fontSize: 14 }} />}
      {children}
    </button>
  );
}

function PlFilterChip({ active, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`portfolio-filter-chip${active ? ' active' : ''}`}
    >
      {children}
    </button>
  );
}
