# Learning & Behavioral Analytics Framework

## Overview
Analytics system to track investor behavior, identify patterns, and provide actionable insights for skill improvement using existing database models.

---

## 📊 Analytics Categories & Data Sources

### 1. RESEARCH BEHAVIOR ANALYTICS

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Time per research step** | `WorkSession.duration`, `TemplateStep` | Identify bottlenecks, optimize workflow | Research Sprint suggestions |
| **Step completion rate** | `ResearchAnswer.status`, `TemplateStep` | Which steps users skip/struggle with | Process improvement alerts |
| **Research velocity** | `ResearchProject.created_at`, `completed_at` | Projects completed per month, trending | Progress visualization |
| **Question quality** | `ResearchAnswer.answer` length, depth | Are users giving thoughtful answers? | Guided prompts for improvement |
| **Session frequency** | `WorkSession.start_time` intervals | Research consistency tracking | Habit formation nudges |
| **Research depth** | `ResearchAnswer` count per project | Surface vs. deep analysis | Quality coaching |

**Implementation:**
```python
# Research Analytics Service
def get_research_behavior_stats(user_id):
    return {
        'avg_time_per_step': calculate_avg_session_time(),
        'completion_rate': get_step_completion_rate(),
        'velocity_trend': projects_per_month(last_6_months),
        'bottleneck_steps': identify_slow_steps(),
        'consistency_score': calculate_session_frequency()
    }
```

---

### 2. INTELLIGENT KILL CHECKLIST ANALYTICS

#### A. Predictive Criterion Effectiveness
**Beyond Simple Counting - Predict Which Ideas Will Survive**

| Analysis Type | Data Mining Approach | Sophisticated Insight | Action |
|---------------|---------------------|----------------------|--------|
| **Early Warning Signals** | Correlation analysis: Which criteria predict eventual kills? | "Companies that fail 'Moat Analysis' have 87% chance of being killed later - move this criterion earlier" | Auto-reorder checklist by predictive power |
| **Criterion Redundancy Detection** | Statistical correlation between criteria | "Debt/Equity and Interest Coverage always fail together - remove redundancy" | Streamline checklist |
| **False Negative Analysis** | Ideas that passed but later became mistakes | "3 mistakes slipped through because you don't check customer concentration - add this criterion" | Plug checklist gaps |
| **Sector-Specific Patterns** | Kill reasons by industry | "For SaaS: Unit economics kills 60%. For Manufacturing: Working capital kills 50%" | Dynamic sector-based checklists |
| **Opportunity Cost Analysis** | Time spent on ideas vs. kill stage | "Average 8 hours wasted on ideas killed at Step 5. ROI of earlier filtering: 40 hours/month saved" | Quantify efficiency gains |

#### B. Standards Drift Detection
**Track How Your Investment Criteria Evolve Over Time**

```python
# Standards Evolution Tracker
def detect_standards_drift(user_id):
    """
    Monitors whether user's acceptance thresholds are drifting over time.
    This helps identify if standards are becoming looser/stricter,
    either intentionally or unconsciously.
    """

    # Analyze criteria thresholds over time periods
    time_periods = [
        ('Q1', get_decisions(user_id, quarter=1)),
        ('Q2', get_decisions(user_id, quarter=2)),
        ('Q3', get_decisions(user_id, quarter=3)),
        ('Q4', get_decisions(user_id, quarter=4))
    ]

    drift_alerts = []

    # For each measurable criterion (debt, margins, growth, etc.)
    for criterion in get_quantifiable_criteria(user_id):
        period_averages = []

        for period_name, decisions in time_periods:
            avg_threshold = calculate_avg_accepted_value(decisions, criterion)
            period_averages.append((period_name, avg_threshold))

        # Calculate drift
        initial_avg = period_averages[0][1]
        current_avg = period_averages[-1][1]
        drift_pct = ((current_avg - initial_avg) / initial_avg) * 100

        # Alert if significant drift detected
        if abs(drift_pct) > 30:  # 30% threshold change
            drift_alerts.append({
                'criterion': criterion.name,
                'direction': 'looser' if drift_pct > 0 else 'stricter',
                'drift_percentage': abs(drift_pct),
                'initial_avg': initial_avg,
                'current_avg': current_avg,
                'trend_data': period_averages,
                'message': f"Your {criterion.name} tolerance has {'increased' if drift_pct > 0 else 'decreased'} by {abs(drift_pct):.0f}% over the year. Is this intentional standard evolution?",
                'question': "Should we update your documented investment criteria to reflect this change?"
            })

    return {
        'standards_stable': len(drift_alerts) == 0,
        'drift_alerts': drift_alerts,
        'evolution_score': calculate_evolution_score(drift_alerts)
    }
```

**Example Alerts:**
- "Your average accepted Debt/Equity ratio was 0.5 in Q1, now 0.9 in Q4 (+80%). Standards evolving or getting loose?"
- "You're now accepting 15% lower profit margins than 6 months ago. Intentional shift to growth stocks?"
- "Your quality bar is getting STRICTER: ROE threshold increased from 12% to 18%"

#### C. Cognitive Bias Detection System
**Identify Psychological Traps in Real-Time**

| Bias Type | Detection Method | Real Example | Intervention |
|-----------|------------------|--------------|--------------|
| **Confirmation Bias** | User researches bullish company 3x longer than bearish | "You spent 12 hours on NVDA (bullish) vs 3 hours on INTC (bearish). Are you seeking confirming evidence?" | Balanced research time prompt |
| **Recency Bias** | Recent market events influence kill criteria | "You added 'Supply Chain Risk' after chip shortage news but never checked it before. Is this data-driven or reactionary?" | Criterion validation check |
| **Anchoring Bias** | First price seen affects valuation tolerance | "Your valuation tolerance changed after seeing TSLA's P/E. You're now accepting higher multiples across all stocks." | Benchmark consistency alert |
| **Herd Mentality** | Kill/promote patterns follow market trends | "Your 'promote' rate increased 40% during bull market vs. your historical baseline. Market euphoria detected." | Anti-FOMO circuit breaker |
| **Sunk Cost Fallacy** | Research time correlates with decision to promote | "You've invested 20 hours in XYZ. Statistical analysis: Ideas with 15+ hours research have same failure rate as 5 hour ideas." | Time-independent decision reminder |

#### D. Kill Probability Prediction System

**Version 1: Rule-Based Pattern Matching (Start Here)**
```python
# Simple Pattern-Based Kill Predictor
def predict_kill_probability_simple(user_id, new_company):
    """
    Uses historical patterns to predict if new idea will be killed.
    No ML required - just pattern matching on user's past decisions.
    """

    # Get user's historical kill patterns
    user_kills = get_kill_history(user_id)

    # Extract patterns from new company
    company_profile = {
        'sector': new_company.sector,
        'market_cap': new_company.market_cap,
        'debt_ratio': new_company.debt_equity_ratio,
        'profit_margin': new_company.net_margin,
        'has_moat': new_company.moat_score > 7,
        'customer_concentration': new_company.top_customer_pct
    }

    # Find similar companies user researched before
    similar_companies = find_similar_historical_companies(user_id, company_profile)

    # Calculate kill rate for similar companies
    if len(similar_companies) >= 3:  # Need minimum sample
        kill_rate = sum(1 for c in similar_companies if c.was_killed) / len(similar_companies)

        # Identify common kill reasons
        common_kill_reasons = []
        for company in [c for c in similar_companies if c.was_killed]:
            common_kill_reasons.append(company.kill_reason)

        most_common_reason = max(set(common_kill_reasons), key=common_kill_reasons.count)

        return {
            'kill_probability': kill_rate,
            'confidence': 'high' if len(similar_companies) >= 5 else 'medium',
            'similar_companies_analyzed': len(similar_companies),
            'pattern': f"You've researched {len(similar_companies)} similar companies and killed {int(kill_rate*100)}%",
            'likely_kill_reason': most_common_reason,
            'recommendation': generate_recommendation(kill_rate, most_common_reason)
        }
    else:
        return {
            'kill_probability': None,
            'message': "Not enough historical data on similar companies to predict."
        }

def generate_recommendation(kill_rate, likely_reason):
    if kill_rate > 0.7:
        return f"High kill probability ({int(kill_rate*100)}%). Check '{likely_reason}' FIRST to save time."
    elif kill_rate > 0.4:
        return f"Moderate kill risk. Pay special attention to '{likely_reason}'."
    else:
        return "Pattern suggests this type passes your filters. Proceed with full research."
```

**Example Output:**
```
New Company: SaaS Startup XYZ
Kill Probability: 75% (High Confidence)
Pattern: "You've researched 8 similar SaaS companies and killed 6 (75%)"
Most Common Kill Reason: "Weak unit economics (LTV/CAC < 3)"
Recommendation: "Check unit economics FIRST before spending time on full research"
```

---

**Version 2: ML-Based Predictor (Future Enhancement)**
```python
# Advanced ML Kill Prediction (implement after collecting 50+ decisions)
def build_kill_prediction_model(user_id):
    """
    Train a gradient boosting model on user's historical decisions.
    Requires minimum 50 kill sessions for statistical validity.
    """

    if get_kill_session_count(user_id) < 50:
        return None  # Not enough data, use simple version

    # Feature engineering from historical data
    features = extract_features_from_kill_sessions(user_id)
    # Features: sector, market_cap, debt_ratio, moat_score, margins, growth, etc.

    # Train model
    X = historical_features
    y = kill_outcomes  # Binary: killed or promoted

    model = train_gradient_boosting_classifier(X, y)

    # Feature importance analysis
    top_predictors = model.feature_importances_

    return {
        'kill_probability_model': model,
        'top_kill_predictors': top_predictors,
        'personalized_insights': [
            f"Your #1 kill predictor: {top_predictors[0].name}",
            f"Red flag threshold for you: {calculate_user_threshold(top_predictors[0])}"
        ]
    }
```

#### E. Personal Performance Benchmarking
**Track Your Progress Against Your Own Past Performance**

| Benchmark | Time Comparison | Insight | Growth Indicator |
|-----------|-----------------|---------|------------------|
| **Kill Efficiency** | Q4 2024 vs Q1 2024 | "You're now killing bad ideas 3 days faster than 6 months ago - process improving!" | Time saved per idea |
| **Research Depth** | This quarter vs last quarter | "You're asking 12 questions/company now vs 8 before. Research quality improving." | Questions per company trend |
| **Mistake Frequency** | Last 6 months vs previous 6 months | "Mistake rate decreased 40% - you're learning from past errors!" | Mistakes per decision |
| **Decision Accuracy** | 2024 vs 2023 | "Your thesis accuracy improved from 60% to 75% - calibration improving!" | Thesis accuracy trend |
| **Process Consistency** | Monthly discipline score | "You completed 90% of research steps this month vs 70% last month" | Completion rate trend |
| **Time to Proficiency** | Learning curve by sector | "Your semiconductor research time dropped from 20h to 12h - expertise building!" | Hours per sector over time |

**Example Dashboard:**
```
Your Year-Over-Year Progress:

Research Efficiency:     ████████░░ 80% (+25% vs last year)
Decision Quality:        ███████░░░ 70% (+15% vs last year)
Process Discipline:      █████████░ 90% (+30% vs last year)
Mistake Reduction:       ████████░░ 80% (50% fewer mistakes)

Biggest Improvement: "Process Discipline"
Focus Area: "Decision Quality" - Consider pre-mortem depth
```

---

---

### 3. DECISION QUALITY TRACKING

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Thesis accuracy** | `DecisionJournal.thesis_accuracy` | How often thesis plays out | Calibration feedback |
| **Confidence vs. outcome** | `DecisionJournal.confidence_score` vs `actual_return` | Overconfident? Underconfident? | Bias detection |
| **Decision speed** | `ResearchProject.completed_at` → `DecisionJournal.created_at` | Analysis paralysis vs. hasty | Tempo coaching |
| **Investment vs. pass ratio** | `DecisionJournal.decision_type` distribution | Too aggressive? Too cautious? | Risk profile insights |
| **Pre-mortem effectiveness** | `key_assumptions` vs `what_went_wrong` | Did you identify real risks? | Pre-mortem training |
| **Learning from outcomes** | `DecisionJournal` → `MistakeLog` → `KillCriterion` | Close the learning loop | Process evolution tracking |

**Anti-FOMO Integration:**

TODO: VIX alone is not a good indicator of Euphoria. We need to other metrices like Shiller PE ratio, historic S&P PE ratio, and other metrics to evaluate the market Euphoria.

```python
# During market euphoria (VIX < 15, ATH conditions)
def euphoria_protection_check(user_id):
    recent_decisions = get_decisions(last_30_days)

    if len(recent_decisions) > user_baseline * 2:
        return {
            'alert': True,
            'message': "You're researching 2x faster than normal during market highs.",
            'prompt': "Historical data: Decisions made during euphoria have 30% worse outcomes.",
            'action': 'cooling_off_period'
        }
```

---

### 4. MISTAKE PATTERN ANALYSIS

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Recurring mistake types** | `MistakeLog.mistake_category` | Valuation? Timing? Thesis? | Targeted learning paths |
| **Costly mistake patterns** | `MistakeLog.financial_cost` aggregated | Where are biggest losses? | Risk management alerts |
| **Time to mistake recognition** | `DecisionJournal.decision_date` → `MistakeLog.created_at` | How fast do you catch errors? | Self-awareness tracking |
| **Learning implementation** | `MistakeLog.lessons` → `KillCriterion` added | Are you adapting your process? | Adaptive checklist prompts |
| **Mistake frequency trend** | `MistakeLog.created_at` time series | Improving over time? | Progress encouragement |
| **Blind spot categories** | Least logged mistake types | What aren't you seeing? | Proactive education |

TODO: An important thing, alerting based on mistake logs during research. In mistake logs, if we can find the sector or step that is relevant, we can alert the user while doing the research.


**Implementation:**
```python
# Mistake Pattern Service
def analyze_mistake_patterns(user_id):
    mistakes = user.mistake_logs.all()

    # Group by category
    categories = defaultdict(list)
    for mistake in mistakes:
        categories[mistake.mistake_category].append(mistake)

    # Find recurring patterns
    patterns = []
    for category, items in categories.items():
        if len(items) >= 2:
            total_cost = sum(m.financial_cost or 0 for m in items)
            patterns.append({
                'category': category,
                'frequency': len(items),
                'total_cost': total_cost,
                'common_factors': extract_common_factors(items),
                'suggested_checklist_item': generate_preventive_check(items)
            })

    return sorted(patterns, key=lambda x: x['total_cost'], reverse=True)
```

---

### 5. LEARNING & GROWTH TRACKING

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Journal entry depth** | `JournalEntry.content` word count, structure | Surface thoughts vs. deep analysis | Writing quality prompts |
| **Review frequency** | `JournalEntry.last_reviewed`, `review_count` | Spaced repetition effectiveness | Review reminders |
| **Insight connection** | `JournalEntry.related_entry_ids` | Building knowledge graph | Second brain visualization |
| **Thesis evolution tracking** | `ThesisEvolution.version` count | How often do you update theses? | Dynamic thinking score |
| **Learning note application** | `LearningNote` → subsequent decisions | Are you applying lessons? | Learning loop closure |
| **Weekly review consistency** | `WeeklyReview.completed_at` | Building reflection habit | Accountability nudges |

**Second Brain Analytics:**
```python
# Knowledge Graph Analysis
def analyze_knowledge_connections(user_id):
    entries = user.journal_entries.all()

    # Build connection graph
    graph = build_connection_graph(entries)

    return {
        'total_insights': len(entries),
        'connected_insights': count_connected_nodes(graph),
        'isolated_insights': count_isolated_nodes(graph),
        'insight_clusters': identify_clusters(graph),
        'strongest_connections': get_top_connections(graph, n=5),
        'knowledge_depth_score': calculate_depth(graph)
    }
```

---

### 6. TIME ALLOCATION INTELLIGENCE

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Research time by company** | `ResearchLog.company_id`, `duration` | Where are you spending time? | Sprint recommendations |
| **Time by research type** | `ResearchLog.activity_type` | What takes longest? | Efficiency coaching |
| **Productive hours** | `ResearchLog.hour_of_day` | When are you most effective? | Schedule optimization |
| **Session length patterns** | `WorkSession.duration` distribution | Short bursts vs. deep work | Sprint vs. marathon guidance |
| **Time to decision** | Research start → `DecisionJournal` | Analysis paralysis indicator | Decision tempo coaching |
| **Interruption patterns** | `WorkSession` gaps | Are sessions fragmented? | Focus improvement tips |

**Research Sprint Suggestions:**
```python
# Sprint Recommendation Engine
def suggest_next_sprint(user_id, available_minutes):
    # Analyze historical session data
    avg_time_per_step = calculate_avg_times(user_id)

    # Find incomplete projects
    active_projects = get_active_projects(user_id)

    # Match tasks to available time
    suggestions = []
    for project in active_projects:
        incomplete_steps = get_incomplete_steps(project)

        for step in incomplete_steps:
            est_time = avg_time_per_step.get(step.template_step.name, 30)

            if est_time <= available_minutes * 1.1:  # 10% buffer
                suggestions.append({
                    'project': project.subject_display_name,
                    'task': step.template_step.name,
                    'estimated_minutes': est_time,
                    'priority': calculate_priority(project, step)
                })

    return sorted(suggestions, key=lambda x: x['priority'], reverse=True)[:3]
```

---

### 7. SECTOR & INDUSTRY EXPERTISE

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Sector concentration** | `Company.sector`, research activity | Circle of competence tracking | Diversification suggestions |
| **Sector expertise depth** | `SectorAnalysis`, `SectorNote` count | Which sectors do you know best? | Expertise visualization |
| **Cross-sector learning** | Research across multiple sectors | Generalist vs. specialist | Learning path recommendations |
| **Industry-specific questions** | `QuestionBankItem.sector` | Custom due diligence by sector | Smart template injection |
| **Competitive analysis depth** | `Company.competitors` relationships | Do you study competition? | Competitive moat coaching |

---

### 8. PROCESS CONSISTENCY & DISCIPLINE

| Metric | Data Source | Insight | User Journey Impact |
|--------|-------------|---------|---------------------|
| **Checklist completion rate** | `ResearchSession.status` | Are you following your process? | Discipline scoring |
| **Template adherence** | `ResearchAnswer` vs `TemplateStep` | Skipping steps? | Process gap alerts |
| **Pre-mortem usage** | `DecisionJournal.key_assumptions` filled | Thinking about risks upfront? | Risk awareness coaching |
| **Post-mortem completion** | `InvestmentPostMortem` records | Learning from outcomes? | Learning loop prompts |
| **Destination tracking** | `DestinationCheckpoint` usage | Monitoring thesis milestones? | Accountability system |
| **Weekly review habit** | `WeeklyReview` consistency | Reflection discipline | Habit formation tracking |

**Discipline Score Calculation:**
```python
# Discipline & Consistency Scoring
def calculate_discipline_score(user_id):
    weights = {
        'checklist_completion': 0.25,
        'pre_mortem_quality': 0.20,
        'post_mortem_completion': 0.15,
        'weekly_review_consistency': 0.15,
        'template_adherence': 0.15,
        'learning_loop_closure': 0.10
    }

    scores = {
        'checklist_completion': get_completion_rate(user_id),
        'pre_mortem_quality': assess_premortem_depth(user_id),
        'post_mortem_completion': get_postmortem_rate(user_id),
        'weekly_review_consistency': get_review_habit_score(user_id),
        'template_adherence': get_step_adherence_rate(user_id),
        'learning_loop_closure': get_learning_application_rate(user_id)
    }

    # Weighted average
    total_score = sum(scores[k] * weights[k] for k in scores)

    return {
        'overall_score': total_score,
        'breakdown': scores,
        'strengths': [k for k, v in scores.items() if v > 0.8],
        'improvement_areas': [k for k, v in scores.items() if v < 0.5]
    }
```

---

## 🎯 KEY ANALYTICS DASHBOARDS TO BUILD

### 1. Learning Progress Dashboard
**Displays:** Discipline score, pattern recognition development, mistake trends, knowledge connections
**User Journey:** Becomes Systematic (Days 15-30)

### 2. Research Efficiency Dashboard
**Displays:** Time allocation, bottleneck steps, sprint suggestions, velocity trends
**User Journey:** Research Sprint (Time-constrained users)

### 3. Pattern Recognition Dashboard
**Displays:** Kill patterns, decision consistency, bias detection, checklist effectiveness
**User Journey:** Pattern Recognition (Week 3+)

### 4. Decision Quality Dashboard
**Displays:** Thesis accuracy, confidence calibration, pre-mortem effectiveness, outcome tracking
**User Journey:** Anti-FOMO (Market conditions awareness)

### 5. Knowledge Graph Dashboard
**Displays:** Connected insights, thesis evolution, learning note application, review consistency
**User Journey:** Second Brain development

---

## 🔧 IMPLEMENTATION PRIORITY

### Phase 1: Foundation (Weeks 1-2)
- [ ] Research behavior analytics service
- [ ] Kill pattern detection system
- [ ] Basic discipline scoring
- [ ] Time allocation tracking

### Phase 2: Pattern Alerts (Weeks 3-4)
- [ ] Pattern recognition alert system
- [ ] Mistake pattern analysis
- [ ] Suggested checklist improvements
- [ ] Learning loop tracking

### Phase 3: Dashboards (Weeks 5-6)
- [ ] Learning progress dashboard
- [ ] Research efficiency dashboard
- [ ] Pattern recognition dashboard
- [ ] Charts & visualizations (ApexCharts)

### Phase 4: Intelligence (Weeks 7-8)
- [ ] Research sprint recommendation engine
- [ ] Anti-FOMO market condition monitoring
- [ ] Second brain knowledge graph
- [ ] Personalized insights generation

---

## 📈 SUCCESS METRICS

**User Engagement:**
- 60%+ users check analytics weekly
- 40%+ users act on pattern alerts
- 25%+ users improve discipline score over 3 months

**Behavior Change:**
- 30% reduction in repeated mistakes
- 50% increase in checklist consistency
- 20% improvement in thesis accuracy

**Platform Stickiness:**
- Analytics viewers have 2x retention rate
- Users with high discipline scores are power users
- Pattern alerts drive daily active usage

---

## 💡 QUICK WINS (Can Implement Now)

1. **Kill Pattern Alerts** - Low hanging fruit, high impact
2. **Research Time Bottleneck Detection** - Uses existing WorkSession data
3. **Discipline Score Badge** - Gamification element
4. **Weekly Email Summary** - Automated from existing data
5. **Mistake Cost Tracker** - Simple aggregation, powerful insight

---

This framework turns raw data into actionable intelligence that helps investors systematically improve their research skills and decision-making process.
