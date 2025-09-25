# Database Usage Patterns and Data Flow

This document outlines how data flows through the Investment Checklist Platform and common usage patterns for different user workflows.

## Core User Workflows

### 1. Investment Idea Lifecycle

#### Stage 1: Idea Capture
```sql
-- User captures a new investment idea
INSERT INTO idea_pipeline (
    user_id, name, idea_type, source,
    thesis_summary, initial_notes, status
) VALUES (...);

-- Log the activity
INSERT INTO research_log (
    user_id, activity_type, idea_id,
    timestamp, details
) VALUES (...);
```

**Tables Involved**: `idea_pipeline`, `research_log`
**Triggers**: User form submission, CSV import, API integration

#### Stage 2: Initial Screening (Kill Checklist)
```sql
-- Start a kill session
INSERT INTO kill_session (
    user_id, idea_id, kill_checklist_id,
    started_at
) VALUES (...);

-- Answer screening questions
INSERT INTO kill_answer (
    kill_session_id, criterion_id,
    passed, notes, answered_at
) VALUES (...);

-- Update idea status based on outcome
UPDATE idea_pipeline
SET status = 'killed', kill_reason = '...', killed_at = NOW()
WHERE id = ?;
```

**Tables Involved**: `kill_session`, `kill_answer`, `idea_pipeline`
**Decision Points**: Pass/fail thresholds, required vs optional criteria

#### Stage 3: Promotion to Research Project
```sql
-- Create research project from survived idea
INSERT INTO research_project (
    user_id, template_id, idea_id, company_id,
    project_name, investment_thesis, status
) VALUES (...);

-- Update idea status
UPDATE idea_pipeline
SET status = 'promoted', promoted_at = NOW()
WHERE id = ?;
```

**Tables Involved**: `research_project`, `idea_pipeline`, `company`
**Business Logic**: Template selection, company association

#### Stage 4: Research Execution
```sql
-- Start work session for specific step
INSERT INTO work_session (
    research_project_id, user_id, step_index,
    step_name, start_time
) VALUES (...);

-- Execute checklist step (if applicable)
INSERT INTO research_session (
    user_id, company_id, checklist_id,
    start_date, status
) VALUES (...);

-- Record research answers
INSERT INTO research_answer (
    research_session_id, checklist_item_id,
    answer_text, satisfaction_status, answered_at
) VALUES (...);

-- Complete work session
UPDATE work_session
SET end_time = NOW(),
    duration_minutes = EXTRACT(EPOCH FROM (NOW() - start_time))/60,
    notes = '...', findings = '...'
WHERE id = ?;
```

**Tables Involved**: `work_session`, `research_session`, `research_answer`
**Complex Logic**: Step type handling, time tracking, progress calculation

#### Stage 5: Decision Making
```sql
-- Record investment decision
INSERT INTO decision_journal (
    user_id, company_id, project_id,
    decision_type, decision_date, confidence_score,
    investment_thesis, expected_return, key_assumptions
) VALUES (...);

-- Update project status
UPDATE research_project
SET status = 'completed', decision = 'invest',
    decision_date = NOW(), completed_at = NOW()
WHERE id = ?;
```

**Tables Involved**: `decision_journal`, `research_project`
**Analytics Impact**: Success rate calculations, performance tracking

### 2. Research Session Workflow

#### Traditional Checklist Research
```sql
-- Query available checklists for user
SELECT c.*, COUNT(ci.id) as item_count
FROM checklist c
LEFT JOIN checklist_item ci ON c.id = ci.checklist_id
WHERE c.user_id = ? OR c.is_public = true
GROUP BY c.id
ORDER BY c.times_used DESC;

-- Start research session
INSERT INTO research_session (
    user_id, company_id, checklist_id, start_date
) VALUES (?, ?, ?, NOW());

-- Retrieve checklist questions (with hierarchy)
WITH RECURSIVE checklist_hierarchy AS (
    SELECT id, text, parent_id, order, 0 as level
    FROM checklist_item
    WHERE checklist_id = ? AND parent_id IS NULL

    UNION ALL

    SELECT ci.id, ci.text, ci.parent_id, ci.order, ch.level + 1
    FROM checklist_item ci
    JOIN checklist_hierarchy ch ON ci.parent_id = ch.id
)
SELECT * FROM checklist_hierarchy ORDER BY level, order;
```

**Performance Considerations**:
- Recursive CTE for hierarchical questions
- Indexed lookups on `checklist_id` and `parent_id`
- Caching for frequently used checklists

#### Research Answer Processing
```sql
-- Save research answer with rich metadata
INSERT INTO research_answer (
    research_session_id, checklist_item_id,
    answer_text, satisfaction_status, answered_at,
    sources, confidence_level, tags
) VALUES (...);

-- Update session progress
UPDATE research_session
SET progress_percentage = (
    SELECT (COUNT(CASE WHEN ra.satisfaction_status IS NOT NULL THEN 1 END) * 100.0) /
           COUNT(*)
    FROM checklist_item ci
    LEFT JOIN research_answer ra ON ci.id = ra.checklist_item_id
                                   AND ra.research_session_id = ?
    WHERE ci.checklist_id = (SELECT checklist_id FROM research_session WHERE id = ?)
)
WHERE id = ?;
```

### 3. Advanced Research Workflow

#### Template-Based Research
```sql
-- Create project from template
SELECT workflow_steps FROM research_template WHERE id = ?;

-- Dynamic step execution based on step type
CASE step.type:
    'checklist' -> Execute traditional checklist research
    'model' -> Load financial model template
    'document_review' -> Present document library
    'external_research' -> Provide research tools
    'analysis' -> Load analysis framework
```

**JSON Processing**: Template steps stored as JSON arrays, processed dynamically

#### Progress Tracking
```sql
-- Calculate project progress
SELECT
    rt.name as template_name,
    rp.current_step_index,
    jsonb_array_length(rp.completed_steps) as completed_count,
    jsonb_array_length(rt.workflow_steps) as total_steps,
    (jsonb_array_length(rp.completed_steps)::float /
     jsonb_array_length(rt.workflow_steps) * 100) as progress_percentage
FROM research_project rp
JOIN research_template rt ON rp.template_id = rt.id
WHERE rp.id = ?;
```

## Common Query Patterns

### 1. Dashboard Queries

#### User Performance Summary
```sql
-- Research metrics aggregation
SELECT
    rm.*,
    (rm.successful_investments::float /
     NULLIF(rm.successful_investments + rm.failed_investments, 0) * 100) as success_rate,
    (rm.total_ideas_killed::float /
     NULLIF(rm.total_ideas_captured, 0) * 100) as kill_rate
FROM research_metrics rm
WHERE rm.user_id = ?;

-- Recent activity timeline
SELECT
    rl.activity_type,
    rl.timestamp,
    rl.details,
    CASE
        WHEN rl.company_id IS NOT NULL THEN c.name
        WHEN rl.idea_id IS NOT NULL THEN ip.name
        WHEN rl.project_id IS NOT NULL THEN rp.project_name
    END as subject_name
FROM research_log rl
LEFT JOIN company c ON rl.company_id = c.id
LEFT JOIN idea_pipeline ip ON rl.idea_id = ip.id
LEFT JOIN research_project rp ON rl.project_id = rp.id
WHERE rl.user_id = ?
ORDER BY rl.timestamp DESC
LIMIT 20;
```

#### Portfolio Overview
```sql
-- Active research projects with progress
SELECT
    rp.id,
    rp.project_name,
    COALESCE(c.name, rp.research_subject_name) as subject,
    rt.name as template_name,
    rp.status,
    (jsonb_array_length(rp.completed_steps)::float /
     jsonb_array_length(rt.workflow_steps) * 100) as progress,
    rp.last_worked_at,
    EXTRACT(days FROM NOW() - rp.last_worked_at) as days_since_activity
FROM research_project rp
JOIN research_template rt ON rp.template_id = rt.id
LEFT JOIN company c ON rp.company_id = c.id
WHERE rp.user_id = ? AND rp.status = 'active'
ORDER BY rp.last_worked_at DESC;
```

### 2. Analytics Queries

#### Behavioral Pattern Analysis
```sql
-- Most productive time analysis
SELECT
    rl.hour_of_day,
    rl.day_of_week,
    COUNT(*) as activity_count,
    AVG(rl.duration_minutes) as avg_duration,
    SUM(CASE WHEN rl.activity_type = 'decision_made' THEN 1 ELSE 0 END) as decisions_made
FROM research_log rl
WHERE rl.user_id = ?
  AND rl.timestamp >= NOW() - INTERVAL '90 days'
GROUP BY rl.hour_of_day, rl.day_of_week
ORDER BY activity_count DESC;

-- Source quality analysis
SELECT
    ip.source,
    COUNT(*) as total_ideas,
    SUM(CASE WHEN ip.status = 'killed' THEN 1 ELSE 0 END) as killed_count,
    SUM(CASE WHEN ip.status = 'promoted' THEN 1 ELSE 0 END) as promoted_count,
    (SUM(CASE WHEN ip.status = 'promoted' THEN 1 ELSE 0 END)::float /
     COUNT(*) * 100) as promotion_rate
FROM idea_pipeline ip
WHERE ip.user_id = ?
GROUP BY ip.source
HAVING COUNT(*) >= 5
ORDER BY promotion_rate DESC;
```

#### Decision Quality Metrics
```sql
-- Investment performance by confidence level
SELECT
    dj.confidence_score,
    COUNT(*) as decision_count,
    AVG(ip.actual_return_percentage) as avg_return,
    STDDEV(ip.actual_return_percentage) as return_volatility,
    SUM(CASE WHEN ip.actual_return_percentage > 0 THEN 1 ELSE 0 END) as winners,
    SUM(CASE WHEN ip.actual_return_percentage <= 0 THEN 1 ELSE 0 END) as losers
FROM decision_journal dj
LEFT JOIN investment_postmortem ip ON dj.id = ip.decision_id
WHERE dj.user_id = ?
  AND dj.decision_type = 'invest'
  AND ip.actual_return_percentage IS NOT NULL
GROUP BY dj.confidence_score
ORDER BY dj.confidence_score;
```

### 3. Learning System Queries

#### Mistake Pattern Recognition
```sql
-- Common mistake categories
SELECT
    ml.mistake_category,
    ml.mistake_subcategory,
    COUNT(*) as frequency,
    SUM(ml.estimated_cost) as total_cost,
    array_agg(DISTINCT ml.root_cause) as common_causes
FROM mistake_log ml
WHERE ml.user_id = ?
  AND ml.created_at >= NOW() - INTERVAL '1 year'
GROUP BY ml.mistake_category, ml.mistake_subcategory
HAVING COUNT(*) >= 2
ORDER BY frequency DESC, total_cost DESC;

-- Learning note review schedule
SELECT
    ln.*,
    CASE
        WHEN ln.next_review_date <= CURRENT_DATE THEN 'due'
        WHEN ln.next_review_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'upcoming'
        ELSE 'future'
    END as review_status
FROM learning_note ln
WHERE ln.user_id = ?
  AND ln.is_archived = false
ORDER BY ln.next_review_date ASC;
```

## Data Integrity Patterns

### 1. Transaction Patterns

#### Research Session Completion
```sql
BEGIN;

-- Update session status
UPDATE research_session
SET status = 'completed',
    conclusion = ?,
    completed_at = NOW()
WHERE id = ?;

-- Calculate satisfaction metrics
INSERT INTO research_metrics_temp
SELECT
    COUNT(*) as total_answers,
    SUM(CASE WHEN satisfaction_status = 'satisfied' THEN 1 ELSE 0 END) as satisfied,
    SUM(CASE WHEN satisfaction_status = 'needs_attention' THEN 1 ELSE 0 END) as needs_attention
FROM research_answer
WHERE research_session_id = ?;

-- Log completion activity
INSERT INTO research_log (
    user_id, activity_type, company_id,
    timestamp, details
) VALUES (?, 'research_completed', ?, NOW(), ?);

COMMIT;
```

#### Project Deletion (with Cascade Cleanup)
```sql
BEGIN;

-- Manual cleanup for non-cascade relationships
UPDATE journal_entry
SET idea_id = NULL
WHERE idea_id = ?;

UPDATE journal_entry
SET project_id = NULL
WHERE project_id = ?;

-- Cascade deletes will handle:
-- - research_log entries (idea_id, project_id)
-- - work_sessions
-- - kill_sessions

DELETE FROM research_project WHERE id = ?;

COMMIT;
```

### 2. Data Validation Patterns

#### Business Rule Enforcement
```sql
-- Ensure decision dates are logical
ALTER TABLE decision_journal
ADD CONSTRAINT check_decision_date
CHECK (decision_date >= created_at::date);

-- Validate confidence scores
ALTER TABLE decision_journal
ADD CONSTRAINT check_confidence_range
CHECK (confidence_score BETWEEN 1 AND 10);

-- Ensure positive durations
ALTER TABLE work_session
ADD CONSTRAINT check_positive_duration
CHECK (duration_minutes IS NULL OR duration_minutes >= 0);
```

## Performance Optimization Strategies

### 1. Query Optimization

#### Index Usage
```sql
-- Efficient timeline queries
CREATE INDEX idx_research_log_user_timestamp
ON research_log (user_id, timestamp DESC);

-- Fast status filtering
CREATE INDEX idx_research_project_user_status
ON research_project (user_id, status)
WHERE status IN ('active', 'paused');

-- Company lookup optimization
CREATE INDEX idx_company_ticker_name
ON company (ticker_symbol, name);
```

#### Materialized Views for Dashboards
```sql
-- Pre-calculated user metrics
CREATE MATERIALIZED VIEW user_dashboard_metrics AS
SELECT
    u.id as user_id,
    COUNT(DISTINCT ip.id) as total_ideas,
    COUNT(DISTINCT CASE WHEN ip.status = 'promoted' THEN ip.id END) as promoted_ideas,
    COUNT(DISTINCT rp.id) as total_projects,
    COUNT(DISTINCT CASE WHEN rp.status = 'completed' THEN rp.id END) as completed_projects,
    SUM(ws.duration_minutes) as total_research_minutes,
    COUNT(DISTINCT dj.id) as total_decisions
FROM user u
LEFT JOIN idea_pipeline ip ON u.id = ip.user_id
LEFT JOIN research_project rp ON u.id = rp.user_id
LEFT JOIN work_session ws ON u.id = ws.user_id
LEFT JOIN decision_journal dj ON u.id = dj.user_id
GROUP BY u.id;

-- Refresh strategy
REFRESH MATERIALIZED VIEW user_dashboard_metrics;
```

### 2. Caching Strategies

#### Application-Level Caching
- User metrics: Cache for 1 hour
- Template definitions: Cache until modified
- Company financial data: Cache daily
- Checklist items: Cache until checklist modified

#### Database-Level Caching
- Query plan caching for complex analytics queries
- Connection pooling for high-concurrency operations
- Read replicas for analytics workloads

## Data Migration Patterns

### 1. Schema Evolution
```sql
-- Add new column with default
ALTER TABLE research_project
ADD COLUMN sentiment_score INTEGER DEFAULT 5;

-- Backfill existing data
UPDATE research_project
SET sentiment_score =
    CASE
        WHEN decision = 'invest' THEN 8
        WHEN decision = 'pass' THEN 3
        ELSE 5
    END
WHERE sentiment_score IS NULL;
```

### 2. Data Cleanup
```sql
-- Remove orphaned records (should be prevented by FK constraints)
DELETE FROM research_answer
WHERE research_session_id NOT IN (
    SELECT id FROM research_session
);

-- Archive old data
INSERT INTO research_log_archive
SELECT * FROM research_log
WHERE timestamp < NOW() - INTERVAL '2 years';

DELETE FROM research_log
WHERE timestamp < NOW() - INTERVAL '2 years';
```

This usage pattern documentation provides guidance for developers working with the Investment Checklist Platform database, covering common workflows, optimization strategies, and maintenance patterns.