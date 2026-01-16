# Portfolio Analytics - Argos Integration Roadmap

**Last Updated:** 2026-01-13
**Goal:** Build dual-layer portfolio analytics (UI + Argos intelligence system)

---

## 🎯 Core Strategy

**Approach:** Complete portfolio analytics piece by piece, then extend to research workflow, finally connect via Argos.

**Data Architecture:**
- **UI Layer:** Direct visualization data (metrics, charts, comparisons)
- **Argos Layer:** Raw intelligence data for correlation analysis and pattern detection

---

## Phase 1: Deep Behavioral Insights (CURRENT FOCUS)

### 1.1 Define UI Requirements
- [ ] List exact metrics for Overview section (Win Rate, Hold Time, ???)
- [ ] Define Behavioral Patterns section content (pattern cards, evidence, severity)
- [ ] Define Winners vs Losers comparison metrics
- [ ] Decide on Risk Analysis visualization
- [ ] Review mockup: `/docs/mockup_option3_portofolio_analytics.html`

**Decisions Needed:**
- What KPIs to show in Overview besides Win Rate and Hold Time?
- Show ALL patterns or only HIGH severity?
- What specific comparisons for Winners vs Losers?

---

### 1.2 Adapt Response Schema
- [ ] Update `portfolio_raw_trade_analysis.yaml` response_schema
- [ ] Add `ui_data` section (formatted for direct rendering)
- [ ] Add `argos_data` section (raw metadata for correlations)
- [ ] Include fields for:
  - Winners vs Losers metrics (avg return, hold time, count)
  - Disposition Effect metadata (severity score, affected stocks, evidence)
  - Pattern detection data (pattern type, severity, trade examples)

**Schema Structure:**
```yaml
{
  "ui_data": {
    "kpis": {...},
    "behavioral_patterns": [...],
    "comparisons": {...}
  },
  "argos_data": {
    "pattern_metadata": {...},
    "affected_stocks": [...],
    "correlation_hints": {...}
  }
}
```

---

### 1.3 Create Database Tables

#### Table 1: `portfolio_ui_insights`
**Purpose:** Direct UI rendering (snapshot-based)

- [ ] Design schema (user_id, generated_at, analysis_period, etc.)
- [ ] Decide: JSONB for flexibility or normalized columns?
- [ ] Fields: kpis, behavioral_patterns, comparisons, evolution_timeline
- [ ] Add indexes for user_id, generated_at

#### Table 2: `portfolio_argos_data`
**Purpose:** Argos correlation engine intelligence

- [ ] Design schema (user_id, analysis_id, pattern_type, etc.)
- [ ] Store: pattern_metadata, affected_stocks, severity_scores
- [ ] Add fields for research correlation hints
- [ ] Enable time-series tracking (detect pattern evolution)

**Key Question:** Normalize patterns into separate rows, or keep as JSONB?

---

### 1.4 Implement Data Storage
- [ ] Update `_normalize_ai_response()` to handle dual schema
- [ ] Create `_split_ui_and_argos_data()` helper method
- [ ] Update `_format_for_template()` to format UI data
- [ ] Create database service for saving to both tables
- [ ] Update Celery task to save to DB after analysis
- [ ] Maintain backward compatibility with cache files

---

### 1.5 UI Integration
- [ ] Update `portfolio_basic_analytics.html` template
- [ ] Implement Winners vs Losers comparison section
- [ ] Add Disposition Effect visualization (conditional)
- [ ] Update Overview section with new KPIs
- [ ] Test rendering with real data
- [ ] Verify caching and performance

---

## Phase 2: Additional Portfolio Insights (FUTURE)

### Analysis Types to Add:
- [ ] Sector momentum chasing detection
- [ ] Position sizing risk analysis
- [ ] Tax optimization opportunities
- [ ] Dividend vs growth allocation

**For Each Analysis:**
1. Define UI + Argos schema
2. Create YAML template
3. Store in same dual tables
4. Update UI to render new sections

---

## Phase 3: Research Workflow Insights (FUTURE)

### Research Data Extraction:
- [ ] Research quality scores
- [ ] Checklist completion rates
- [ ] Exit criteria documentation
- [ ] Thesis evolution tracking
- [ ] Time spent researching per position

### Database:
- [ ] Create `research_ui_insights` table
- [ ] Create `research_argos_data` table
- [ ] Link to portfolio data via company_id + date range

---

## Phase 4: Argos Correlation Engine (FUTURE)

### Graph-Based Intelligence:

**Node 1:** Portfolio Pattern Detector
- Input: Transaction history
- Output: Detected patterns (Disposition Effect, FOMO, etc.)

**Node 2:** Research Quality Checker
- Input: Pattern type + affected stocks
- Output: Research quality metrics for those stocks

**Node 3:** Correlation Analyzer
- Input: Pattern data + Research data
- Output: Specific correlations found

**Node 4:** Insight Generator
- Input: Correlations
- Output: Actionable insights

### First Flow to Implement:
- [ ] Disposition Effect → Exit Criteria check
- [ ] Define correlation logic
- [ ] Create insight templates
- [ ] Test with real data

---

## Technical Debts / Future Work

### FOMO Detection Enhancement
- [ ] Add price momentum data integration
- [ ] Calculate CAGR thresholds by holding period
- [ ] Detect exits below 25% of peak
- [ ] Integrate market sentiment data

### Research Quality Score
- [ ] Define calculation formula
- [ ] Link transactions to research projects
- [ ] Calculate average for research-backed trades

### Position Sizing Risk
- [ ] Add user-configurable thresholds
- [ ] Store preferences in user settings
- [ ] Dynamic risk level calculation

### User Configuration
- [ ] Text input bot for tuning investment style
- [ ] Configure what is/isn't a risk (e.g., concentration)
- [ ] Set personal thresholds and preferences

---

## Immediate Next Steps (This Session)

**Target:** Complete Phase 1.1 and 1.2

1. **Brainstorm UI Requirements (30 min)**
   - List all metrics for Overview
   - Define Behavioral Patterns display format
   - Decide on comparison metrics

2. **Design Dual Schema (45 min)**
   - Separate UI data from Argos data
   - Update YAML template
   - Document field mappings

3. **Validate with Mockup**
   - Cross-reference with mockup HTML
   - Ensure all UI elements have data source

---

## Questions to Answer

### UI Layer:
1. Overview KPIs: Besides Win Rate and Hold Time, what else?
   - Total return %?
   - Best/worst trade?
   - Portfolio value vs cost?

2. Behavioral Patterns: Show all or filter by severity?

3. Evolution Timeline: Expandable phases or inline metrics?

### Argos Layer:
1. What metadata needed for Disposition Effect correlation?
   - Losing stocks list + hold times?
   - Severity score (0-100)?
   - Evidence trades with dates?

2. How to link portfolio data → research data?
   - Via company_id + date range?
   - Exact match or fuzzy matching?

### Database:
1. JSONB (flexible) vs Normalized columns (queryable)?
2. Store full AI response or parsed fields only?
3. How to handle schema evolution over time?

---

## Success Criteria

**Phase 1 Complete When:**
- ✅ UI shows meaningful behavioral insights
- ✅ Data stored in both UI and Argos tables
- ✅ Winners vs Losers comparison functional
- ✅ Disposition Effect detected and visualized
- ✅ Cache invalidation working correctly

**Argos Ready When:**
- ✅ Raw pattern metadata stored
- ✅ Affected stocks tracked
- ✅ Correlation hints prepared
- ✅ Time-series data available for pattern evolution

---

## Notes

- **Focus:** No scope creep. Complete one phase before moving to next.
- **Philosophy:** Lay groundwork for Argos, don't build full Argos yet.
- **Iteration:** Get basic version working, then enhance.
- **Data Quality:** Garbage in = garbage out. Ensure clean transaction data.
