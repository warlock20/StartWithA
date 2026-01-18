# Portfolio Analytics - Argos Integration Roadmap

**Last Updated:** 2026-01-16
**Goal:** Build portfolio analytics UI + independent Argos intelligence backend
**Status:** Phase 1 COMPLETE ✅ (including Smart Routing milestone)

---

## 🎯 Core Strategy

**Approach:** Complete portfolio analytics UI first, then build Argos as a separate multi-agent backend system.

**Architecture Separation:**
- **AI Analytics (Current):** Human-readable insights from raw transactions → UI visualization
- **Argos (Future):** Independent multi-agent backend that queries DB directly → Correlation detection

**Key Insight:** All raw data exists in the database. Argos doesn't need AI-generated metadata—it queries structured DB tables directly (transactions, positions, research_project, decision_journal, checklist). This keeps systems decoupled, deterministic, and scalable.

---

## Phase 1: Portfolio Analytics UI ✅ COMPLETE

### 1.1 Complete UI Implementation ✅
- [x] Define KPIs: Win Rate, CAGR, Avg Hold Time
- [x] Design pattern cards with collapsible evidence sections
- [x] Create horizontal evolution timeline
- [x] Add FOMO trades table
- [x] Add repeating mistakes list
- [x] Build Winners vs Losers comparison section
- [x] Update extraction methods to populate new UI fields
- [x] Add CAGR calculation using `financial_utils.py`

### 1.2 Testing & Polish ✅
- [x] Test complete flow with re-run analysis
- [x] Verify all UI sections render correctly
- [x] Check severity detection logic accuracy
- [x] Validate CAGR calculations
- [x] Test cache invalidation

### 1.3 AI Service Infrastructure Improvements ✅
- [x] Refactor AI service API for consistency
  - Removed confusing `generate()` method, use `generate_text()` directly
  - Added config parameters (temperature, max_tokens, top_p, top_k, stop_sequences) to all methods
  - Unified interface across `generate_text()`, `generate_json()`, `generate_embeddings()`
- [x] Fix system_context passing to providers
  - Added `system_context` extraction in `_get_task_config()`
  - Updated `_call_provider_to_generate_json()` to pass system context as 'system' kwarg
  - Verified Gemini uses `system_instruction` and Claude uses `system` parameter correctly
- [x] Changed severity detection from fuzzy keywords to AI-provided enum (high/medium/low)
- [x] Fixed CAGR calculation (removed double-counting of reinvested proceeds)
- [x] Fixed Winners vs Losers average returns (reconstruct cost basis from transactions)

### 1.4 Smart Routing & Background Task Handling ✅ COMPLETE
**Goal:** Improve UX when background tasks are running

**Implemented Solution:**
- [x] Composite task_type format: `'portfolio_analysis:{template_name}'`
- [x] Reordered route checks: Running task → Cached results → Force refresh → Placeholder
- [x] Prevents duplicate tasks of same type
- [x] Allows concurrent different analysis types (e.g., behavioral + risk)
- [x] Consistent UX regardless of navigation path

**Technical Implementation:**
- Modified `start_portfolio_analysis()` to check for existing running tasks before creating new ones
- Updated route queries to use composite task_type for granular control
- Added `parse_task_type()` utility function for future enhancements
- Fixed priority: Running task check happens FIRST (prevents showing stale cache)

**Files Modified:**
- `/app/services/background_tasks.py` - Composite task_type, duplicate prevention
- `/app/portfolio/routes.py` - Reordered checks, composite queries

**Future Enhancements (Phase 1.4.1):**
- [ ] Enhance loading page to show:
  - Which specific analysis is running (parse task_type to display "Behavioral Analysis")
  - Progress percentage (if available)
  - Estimated time remaining
  - List of queued tasks (if multiple types running)

**Benefits Achieved:**
- ✅ Consistent UX regardless of navigation path
- ✅ No duplicate tasks wasted
- ✅ Foundation for multiple concurrent background tasks
- ✅ No database migration required

### 1.5 Database Storage (Optional Enhancement)
**Note:** Currently using file cache. DB storage can be added later.

- [ ] Create `portfolio_ui_insights` table (user_id, generated_at, insights_json)
- [ ] Store AI analysis results in DB alongside file cache
- [ ] Add endpoint to retrieve historical analyses
- [ ] Enable trend tracking over time

---

## Phase 2: Additional Portfolio Insights (FUTURE)

### Analysis Types to Add:
- [ ] Sector momentum chasing detection
- [ ] Position sizing risk analysis
- [ ] Tax optimization opportunities
- [ ] Dividend vs growth allocation

**For Each Analysis:**
1. Create YAML prompt template
2. Define UI visualization components
3. Update analytics template
4. Add to UI rendering

---

## Phase 3: Research Workflow Analytics (FUTURE)

### AI-Powered Research Insights:
- [ ] Research quality scoring (from checklist completion)
- [ ] Exit criteria documentation patterns
- [ ] Thesis evolution tracking
- [ ] Time-to-decision metrics
- [ ] Correlation: Research depth vs Trade outcomes

### UI Components:
- [ ] Create `research_analytics.html` template
- [ ] Research quality timeline visualization
- [ ] Thesis evolution narrative
- [ ] Entry/Exit criteria compliance tracker

---

## Phase 4: Argos - Independent Intelligence Backend (FUTURE)

**Philosophy:** Argos is NOT a consumer of AI analytics. It's an independent multi-agent system that queries raw database tables directly.

### System Architecture:

**Input Layer:** Direct SQL queries to:
- `transaction` table → Trade history, hold times, realized G/L
- `portfolio_position` → Active positions, cost basis
- `research_project` → Research depth, quality scores
- `decision_journal` → Entry/exit criteria, thesis changes
- `checklist` → Due diligence completeness

**Processing Layer:** Multi-agent graph
- **Agent 1:** Pattern Detection (algorithmic, not LLM)
  - Queries transactions → Detects disposition effect mathematically
  - Output: Affected stocks, hold time deltas, severity scores

- **Agent 2:** Research Quality Analyzer
  - Queries research_project + checklist for stocks from Agent 1
  - Output: Research quality scores per affected stock

- **Agent 3:** Correlation Engine
  - Combines outputs from Agent 1 + Agent 2
  - Runs statistical correlation analysis
  - Output: "Disposition effect stocks have 60% lower research quality"

- **Agent 4:** Insight Generator (LLM-based)
  - Takes correlation data + generates human-readable insight
  - Output: Actionable recommendation with evidence

**Output Layer:**
- Store in `argos_intelligence` table
- Trigger notifications for high-severity patterns
- Surface in UI as "Argos Insights" panel

### First Flow to Build:
- [ ] Agent 1: Detect disposition effect from transactions table
- [ ] Agent 2: Pull research quality for affected stocks
- [ ] Agent 3: Calculate correlation coefficient
- [ ] Agent 4: Generate insight narrative
- [ ] Test end-to-end with real user data

### Why This Works:
- ✅ Deterministic (not reliant on LLM interpretation)
- ✅ Fresh data (queries DB, not cached AI responses)
- ✅ Scalable (can add new data sources without re-running AI analytics)
- ✅ Decoupled (Argos evolves independently)
- ✅ Multi-domain (can correlate portfolio + research + market data + news)

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

### Historical Price Data Limitations (Deferred)
**Known Issue:** Yahoo Finance returns no historical data for many European stocks (`.F`, `.DE`, `.SW`, `.AS` tickers)

**Impact:**
- Periods where price data unavailable fall back to transaction cost_basis
- Results in portfolio value = cost for those periods
- Affects CAGR calculation accuracy when many holdings lack data

**Observed Examples:**
- `R6C.F`, `GAZ.F`, `TWR.F`, `TATB.F` - no data available
- Multiple European tickers with sparse or missing historical data

**Current Mitigation:**
- Fallback to cost_basis when historical price unavailable
- Nearest date matching within 7-day window for weekends/holidays
- Comprehensive logging to track data sources

**Potential Solutions (Future):**
- [ ] Integrate alternative data provider (Alpha Vantage, Polygon.io, etc.)
- [ ] Manual price data entry for critical holdings
- [ ] Transaction-based approximation (calculate from realized G/L patterns)
- [ ] Multi-provider fallback strategy (try Yahoo → fallback to Alpha Vantage)

**Priority:** Low - Deferred for now (not main priority)

---

## Immediate Next Steps

**Status:** Phase 1 COMPLETE ✅ (January 16, 2026)

**Phase 1 Completed:**
- ✅ Portfolio analytics UI fully implemented
- ✅ AI service infrastructure improved (system_context passing, config parameters)
- ✅ Severity detection using AI enum instead of fuzzy matching
- ✅ CAGR and Winners vs Losers calculations fixed and validated
- ✅ All UI sections rendering correctly with collapsible evidence

**Ready for Phase 2 or Phase 3:**

**Option 1: Phase 2 - Additional Portfolio Insights**
- Add sector momentum chasing detection
- Implement position sizing risk analysis
- Tax optimization opportunities
- Dividend vs growth allocation

**Option 2: Phase 3 - Research Workflow Analytics**
- Research quality scoring from checklist completion
- Exit criteria documentation patterns
- Thesis evolution tracking
- Correlation: Research depth vs Trade outcomes

**Option 3: Phase 1.4 - Database Storage (Optional)**
- Store AI analysis results in DB for historical tracking
- Enable trend visualization over time

---

## Success Criteria

**Phase 1 Complete When:**
- ✅ UI shows all agreed sections (KPIs, patterns, evolution, FOMO, mistakes)
- ✅ Collapsible evidence sections work smoothly
- ✅ Winners vs Losers comparison displays correctly
- ✅ CAGR calculated accurately
- ✅ Severity auto-detection working
- ✅ Cache invalidation functional

**Argos Ready When (Phase 4):**
- ✅ Multi-agent graph architecture defined
- ✅ First correlation flow working (Disposition Effect → Research Quality)
- ✅ DB queries optimized for performance
- ✅ Insight generation producing actionable recommendations
- ✅ System scalable for additional data domains

---

## Notes

- **Focus:** Complete Phase 1 fully before thinking about Phase 2-4
- **Philosophy:** Argos is independent—don't couple it to AI analytics
- **Architecture:** Keep AI Analytics (human insights) and Argos (machine intelligence) separate
- **Data Quality:** All intelligence depends on clean, structured DB data
