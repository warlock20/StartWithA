# Investment Checklist Platform - Database Schema Documentation

## Overview

The Investment Checklist Platform uses a comprehensive PostgreSQL database schema designed to support advanced investment research workflows, decision tracking, and learning analytics. The database consists of **32 main tables** and **2 association tables** that handle all aspects of investment research, idea management, and portfolio tracking.

## Database Architecture

### Core Design Principles

1. **User-Centric Design**: All data is owned by users with proper isolation
2. **Flexible Workflow Support**: JSON fields enable customizable research processes
3. **Comprehensive Audit Trail**: Detailed logging of all activities and decisions
4. **Learning Integration**: Built-in systems for mistake tracking and pattern recognition
5. **Performance Optimization**: Strategic indexing and denormalized metrics tables

### Technology Stack

- **Database**: PostgreSQL with JSON support
- **ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Migration**: Alembic for schema versioning
- **Constraints**: Foreign key constraints with CASCADE deletes for data integrity

## Table Categories

### 1. Core User Management
- `user` - User accounts and authentication
- `favorite_companies` (association) - User-company favorites

### 2. Company and Market Data
- `company` - Company profiles and basic information
- `competitors_association` (association) - Company competitor relationships
- `financial_data` - Historical financial metrics
- `company_document` - Document storage and management
- `company_article` - News articles and external content

### 3. Research and Analysis Tools
- `checklist` - Research checklist templates
- `checklist_item` - Individual checklist questions
- `checklist_analysis` - Active research sessions
- `checklist_answer` - Answers to research questions
- `qualitative_analysis` - Structured analysis (SWOT, etc.)
- `scuttlebutt_analysis` - AI-generated company summaries
- `destination_checkpoint` - Expected future milestones

### 4. Idea Pipeline Management
- `idea_pipeline` - Investment ideas before research
- `kill_checklist` - Quick screening templates
- `kill_criterion` - Individual screening questions
- `kill_session` - Screening session tracking
- `kill_answer` - Screening question answers

### 5. Advanced Research Workflow
- `research_template` - Reusable research workflows
- `research_project` - Active research project execution
- `work_session` - Individual work session tracking
- `template_step` - Library of reusable research steps

### 6. Decision and Learning Management
- `decision_journal` - Investment decision tracking
- `journal_entry` - Enhanced journal entries
- `journal_attachment` - File attachments for journals
- `thesis_evolution` - Investment thesis tracking over time
- `learning_note` - Structured learning and insights

### 7. Analytics and Performance Tracking
- `research_metrics` - Aggregated user performance metrics
- `idea_source_analysis` - Quality analysis of idea sources
- `research_log` - Detailed activity logging
- `mistake_log` - Mistake tracking and analysis
- `weekly_review` - Structured weekly reviews
- `investment_postmortem` - Post-investment analysis
- `pattern_recognition` - Behavioral pattern tracking

### 8. Utility and Support Tables
- `question_bank_item` - Reusable research questions
- `sector_analysis` - Sector-specific research notes
- `journal_template` - Journal entry templates
- `learning_path` - Structured learning paths
- `document_import` - Document import tracking

---

## Detailed Table Specifications

### User Management

#### `user` Table
**Purpose**: Core user authentication and profile management

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique user identifier |
| username | String(64) | NOT NULL, UNIQUE, INDEXED | User login name |
| email | String(120) | NOT NULL, UNIQUE, INDEXED | User email address |
| password_hash | String(256) | | Hashed password for security |
| subscription_tier | String(50) | NOT NULL, DEFAULT='free' | User subscription level |

**Key Relationships**:
- One-to-many with almost all other tables as creator/owner
- Many-to-many with `Company` through `favorite_companies`
- One-to-one with `ResearchMetrics`

**Cascade Behavior**: Most child relationships use `cascade='all, delete-orphan'`

---

### Company and Market Data

#### `company` Table
**Purpose**: Stores company information for investment research

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique company identifier |
| name | String(150) | NOT NULL | Company name |
| ticker_symbol | String(20) | NOT NULL, INDEXED | Stock ticker symbol |
| user_id | Integer | NOT NULL, FK(user.id) | Company creator |
| summary | Text | NULLABLE | Company description |
| sector | String(100) | NULLABLE | Business sector |
| industry | String(150) | NULLABLE | Specific industry |
| intrinsic_value | BigInteger | NULLABLE | Calculated intrinsic value |
| is_in_portfolio | Boolean | NOT NULL, DEFAULT=False, INDEXED | Portfolio membership |

**Key Relationships**:
- Self-referential many-to-many through `competitors_association`
- One-to-many: research sessions, documents, articles, financial data
- Many-to-many with `User` through `favorite_companies`

#### `financial_data` Table
**Purpose**: Historical financial metrics for companies

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique record identifier |
| company_id | Integer | NOT NULL, FK(company.id) | Related company |
| statement_type | String(50) | NOT NULL, INDEXED | Statement type (income, balance, cash flow) |
| metric_name | String(100) | NOT NULL, INDEXED | Metric name |
| period_date | Date | NOT NULL, INDEXED | Reporting period date |
| value | BigInteger | NOT NULL | Metric value |

**Unique Constraint**: `company_id, metric_name, period_date`
**Purpose**: Prevents duplicate financial data entries

---

### Research System

#### `checklist` Table
**Purpose**: User-defined research checklist templates

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique checklist identifier |
| name | String(120) | NOT NULL | Checklist name |
| description | String(1000) | NULLABLE | Checklist description |
| user_id | Integer | NOT NULL, FK(user.id) | Checklist creator |

**Relationships**: One-to-many with `ChecklistItem` (cascade delete)

#### `checklist_item` Table
**Purpose**: Individual questions within research checklists

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique item identifier |
| text | String(500) | NOT NULL | Question text |
| checklist_id | Integer | NOT NULL, FK(checklist.id) | Parent checklist |
| parent_id | Integer | NULLABLE, FK(checklist_item.id) | Parent item (for sub-items) |
| order | Integer | DEFAULT=0 | Display order |
| llm_prompt | Text | NULLABLE | AI assistance prompt |

**Self-Referential**: Supports hierarchical checklist structures
**AI Integration**: LLM prompts enable AI-assisted analysis

#### `checklist_analysis` Table
**Purpose**: Active research sessions using checklists on companies

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique session identifier |
| start_date | DateTime | NOT NULL, DEFAULT=utcnow | Session start time |
| status | String(50) | NOT NULL, DEFAULT='in_progress' | Session status |
| user_id | Integer | NOT NULL, FK(user.id) | Session owner |
| company_id | Integer | NOT NULL, FK(company.id) | Target company |
| checklist_id | Integer | NOT NULL, FK(checklist.id) | Used checklist |
| conclusion | Text | NULLABLE | Session conclusion |

**Relationships**: One-to-many with `ChecklistAnswer` (cascade delete)

#### `checklist_answer` Table
**Purpose**: Individual answers to checklist questions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique answer identifier |
| answer_text | Text | NULLABLE | Answer content |
| answered_at | DateTime | DEFAULT=utcnow | Answer timestamp |
| satisfaction_status | String(30) | DEFAULT='neutral' | Answer satisfaction level |
| checklist_analysis_id | Integer | NOT NULL, FK(checklist_analysis.id) | Parent session |
| checklist_item_id | Integer | NOT NULL, FK(checklist_item.id) | Answered question |

**Status Values**: 'satisfied', 'unsatisfied', 'neutral', 'needs_attention'

---

### Idea Pipeline System

#### `idea_pipeline` Table
**Purpose**: Investment ideas before they become research projects

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique idea identifier |
| user_id | Integer | NOT NULL, FK(user.id) | Idea creator |
| name | String(200) | NOT NULL | Idea name |
| idea_type | String(50) | NOT NULL, DEFAULT='company' | Subject type |
| idea_purpose | String(50) | NOT NULL, DEFAULT='investment' | Purpose |
| ticker_symbol | String(20) | NULLABLE | Stock ticker if applicable |
| company_id | Integer | NULLABLE, FK(company.id) | Associated company |
| source | String(200) | NULLABLE | Idea source |
| thesis_summary | Text | NULLABLE | Initial investment thesis |
| initial_notes | Text | NULLABLE | Initial observations |
| status | String(50) | DEFAULT='inbox', INDEXED | Current status |
| kill_reason | Text | NULLABLE | Reason if killed |
| failed_criterion_id | Integer | NULLABLE, FK(kill_criterion.id) | Failed screening criterion |
| created_at | DateTime | DEFAULT=utcnow | Creation timestamp |
| killed_at | DateTime | NULLABLE | Kill timestamp |
| promoted_at | DateTime | NULLABLE | Promotion timestamp |
| last_reviewed_at | DateTime | NULLABLE | Last review timestamp |
| priority | Integer | DEFAULT=0 | Priority level |
| promoted_to_company_id | Integer | NULLABLE, FK(company.id) | Promoted to company |

**Status Values**: 'inbox', 'reviewing', 'promoted', 'killed', 'paused'
**Cascade Relationships**: One-to-many with `KillSession`

#### `kill_checklist` Table
**Purpose**: Templates for quickly screening investment ideas

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique checklist identifier |
| user_id | Integer | NOT NULL, FK(user.id) | Checklist creator |
| name | String(200) | NOT NULL | Checklist name |
| description | Text | NULLABLE | Checklist description |
| is_default | Boolean | DEFAULT=False | Default checklist flag |
| applicable_to | String(100) | DEFAULT='all' | Applicable idea types |
| total_ideas_evaluated | Integer | DEFAULT=0 | Usage counter |
| total_ideas_killed | Integer | DEFAULT=0 | Kill counter |
| created_at | DateTime | DEFAULT=utcnow | Creation timestamp |
| updated_at | DateTime | DEFAULT=utcnow | Last update timestamp |

**Computed Properties**:
- `kill_rate`: Percentage of ideas killed using this checklist
- `criteria_count`: Number of criteria in this checklist

---

### Advanced Research Workflow

#### `research_template` Table
**Purpose**: Reusable research workflow templates

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique template identifier |
| user_id | Integer | NOT NULL, FK(user.id) | Template creator |
| name | String(200) | NOT NULL | Template name |
| description | Text | NULLABLE | Template description |
| investment_style | String(100) | NULLABLE | Applicable investment style |
| research_subject_types | JSON | NULLABLE | Supported subject types array |
| workflow_steps | JSON | NOT NULL | Structured workflow definition |
| is_public | Boolean | DEFAULT=False | Public template flag |
| is_active | Boolean | DEFAULT=True | Active template flag |
| times_used | Integer | DEFAULT=0 | Usage counter |
| successful_investments | Integer | DEFAULT=0 | Success counter |
| failed_investments | Integer | DEFAULT=0 | Failure counter |
| average_research_hours | Float | NULLABLE | Average research time |
| created_at | DateTime | DEFAULT=utcnow | Creation timestamp |
| updated_at | DateTime | DEFAULT=utcnow | Last update timestamp |

**Computed Properties**:
- `success_rate`: Success percentage
- `step_count`: Number of workflow steps

**JSON Structure - workflow_steps**:
```json
[
  {
    "order": 1,
    "name": "Initial Screening",
    "type": "checklist",
    "config": {
      "checklist_items": [...]
    },
    "required": true,
    "estimated_minutes": 30
  }
]
```

#### `research_project` Table
**Purpose**: Active execution of research templates

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique project identifier |
| user_id | Integer | NOT NULL, FK(user.id) | Project owner |
| template_id | Integer | NOT NULL, FK(research_template.id) | Used template |
| research_subject_type | String(50) | NOT NULL, DEFAULT='company' | Subject type |
| research_subject_name | String(200) | NULLABLE | Subject name |
| company_id | Integer | NULLABLE, FK(company.id) | Associated company |
| idea_id | Integer | NULLABLE, FK(idea_pipeline.id) | Source idea |
| project_name | String(200) | NULLABLE | Project name |
| investment_thesis | Text | NULLABLE | Current investment thesis |
| current_step_index | Integer | DEFAULT=0 | Current workflow step |
| completed_steps | JSON | DEFAULT=[] | Completed step indices |
| step_notes | JSON | DEFAULT={} | Notes per step |
| step_results | JSON | DEFAULT={} | Results per step |
| status | String(50) | DEFAULT='active' | Project status |
| kill_reason | Text | NULLABLE | Reason if killed |
| total_hours_spent | Float | DEFAULT=0.0 | Total research time |
| time_per_step | JSON | DEFAULT={} | Time spent per step |
| last_worked_at | DateTime | NULLABLE | Last activity timestamp |
| decision | String(50) | NULLABLE | Final decision |
| decision_date | DateTime | NULLABLE | Decision timestamp |
| decision_confidence | Integer | NULLABLE | Decision confidence (1-10) |
| decision_notes | Text | NULLABLE | Decision rationale |
| investment_amount | Float | NULLABLE | Investment amount |
| investment_date | Date | NULLABLE | Investment date |
| exit_date | Date | NULLABLE | Exit date |
| return_percentage | Float | NULLABLE | Investment return |
| key_findings | JSON | DEFAULT=[] | Key findings array |
| red_flags | JSON | DEFAULT=[] | Red flags array |
| green_flags | JSON | DEFAULT=[] | Green flags array |
| created_at | DateTime | DEFAULT=utcnow | Creation timestamp |
| completed_at | DateTime | NULLABLE | Completion timestamp |

**Status Values**: 'active', 'paused', 'completed', 'killed'
**Decision Values**: 'invest', 'pass', 'watch', 'exit'

**Computed Properties**:
- `progress_percentage`: Completion percentage
- `current_step`: Current workflow step details
- `is_overdue`: Whether project is behind schedule
- `research_subject`: Formatted subject name

---

### Analytics and Metrics

#### `research_metrics` Table
**Purpose**: Aggregated performance metrics per user

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique metrics identifier |
| user_id | Integer | NOT NULL, UNIQUE, FK(user.id) | Metrics owner |

**Idea Pipeline Metrics**:
- `total_ideas_captured`, `total_ideas_killed`, `total_ideas_promoted` (Integer)
- `overall_kill_rate`, `kill_rate_last_30_days` (Float)
- `ideas_per_source` (JSON) - Source breakdown
- `top_kill_reasons` (JSON) - Common kill reasons

**Research Metrics**:
- `total_research_hours`, `avg_research_hours_per_idea` (Float)
- `checklist_analysiss_completed` (Integer)
- `most_used_checklists` (JSON)

**Decision Quality Metrics**:
- `total_investment_decisions`, `total_pass_decisions` (Integer)
- `avg_decision_confidence` (Float)
- `decisions_by_confidence_level` (JSON)

**Success Tracking**:
- `successful_investments`, `failed_investments` (Integer)
- `total_portfolio_return`, `avg_investment_return` (Float)
- `best_performing_investment`, `worst_performing_investment` (JSON)

**Time and Behavioral Analysis**:
- `most_productive_time_of_day`, `most_productive_day_of_week` (String)
- `avg_session_duration_minutes` (Float)
- `longest_research_streak_days`, `current_research_streak_days` (Integer)

**Source Quality Analysis**:
- `source_quality_rankings` (JSON) - Performance by source
- `source_diversification_score` (Float)

| last_updated | DateTime | DEFAULT=utcnow | Last metrics update |

**Unique Constraint**: One record per user

#### `research_log` Table
**Purpose**: Detailed activity logging for behavioral analysis

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY | Unique log identifier |
| user_id | Integer | NOT NULL, FK(user.id) | Activity user |
| activity_type | String(50) | NOT NULL | Activity type |
| idea_id | Integer | NULLABLE, FK(idea_pipeline.id) CASCADE | Related idea |
| company_id | Integer | NULLABLE, FK(company.id) | Related company |
| project_id | Integer | NULLABLE, FK(research_project.id) CASCADE | Related project |
| details | JSON | NULLABLE | Activity-specific data |
| duration_minutes | Integer | NULLABLE | Activity duration |
| timestamp | DateTime | NOT NULL, INDEXED | Activity timestamp |
| day_of_week | Integer | NOT NULL | Day (0=Monday, 6=Sunday) |
| hour_of_day | Integer | NOT NULL | Hour (0-23) |

**Activity Types**: 'idea_captured', 'idea_killed', 'research_started', 'step_completed', 'decision_made', etc.

**Critical Note**: Uses CASCADE delete on `idea_id` and `project_id` foreign keys to prevent constraint violations during deletions.

---

## Advanced Features

### JSON Field Structures

#### Workflow Steps (`research_template.workflow_steps`)
```json
[
  {
    "order": 1,
    "name": "Management Quality Assessment",
    "type": "checklist",
    "config": {
      "checklist_items": [
        {
          "item": "CEO track record evaluation",
          "prompt": "Analyze CEO's previous experience and achievements"
        }
      ]
    },
    "required": true,
    "estimated_minutes": 45
  },
  {
    "order": 2,
    "name": "Financial Analysis",
    "type": "model",
    "config": {
      "model_type": "dcf"
    },
    "required": true,
    "estimated_minutes": 90
  }
]
```

#### Research Results (`research_project.key_findings`)
```json
[
  {
    "category": "competitive_advantage",
    "finding": "Strong network effects in core platform",
    "confidence": 8,
    "source": "management_interview"
  }
]
```

### Relationship Patterns

#### Cascade Delete Hierarchy
```
User (root)
├── IdeaPipeline (cascade delete)
│   └── ResearchLog (cascade delete)
├── ResearchProject (cascade delete)
│   └── WorkSession (cascade delete)
└── Company
    ├── ChecklistAnalysis
    └── FinancialData
```

#### Many-to-Many Relationships
- `User ↔ Company` (favorites)
- `Company ↔ Company` (competitors)

#### Self-Referential Relationships
- `ChecklistItem.parent_id` → hierarchical questions
- `Company` competitors → peer analysis

### Performance Optimizations

#### Strategic Indexing
- **Timestamp fields**: `created_at`, `timestamp` for time-based queries
- **Status fields**: `status`, `is_active` for filtering
- **Foreign keys**: All relationship fields automatically indexed
- **Lookup fields**: `ticker_symbol`, `sector` for search functionality

#### Denormalization
- `ResearchMetrics`: Pre-calculated aggregations for dashboard performance
- Counter fields: `times_used`, `total_ideas_evaluated` for quick statistics
- Computed properties: Available as model methods for complex calculations

### Data Integrity Features

#### Unique Constraints
- Prevent duplicate financial data: `(company_id, metric_name, period_date)`
- One metrics record per user: `user_id` unique in `ResearchMetrics`
- One sector analysis per user per sector: `(user_id, sector_name)`

#### Foreign Key Constraints
- **Standard**: Maintain referential integrity
- **CASCADE**: `ResearchLog.idea_id`, `ResearchLog.project_id` - Critical for deletion workflows
- **Nullable**: Allow gradual data population and optional relationships

#### Audit Trail
- Comprehensive timestamp tracking across all tables
- Activity logging in `ResearchLog` for behavioral analysis
- Version tracking in `ThesisEvolution` for investment thesis changes

---

## Migration and Versioning

### Database Migrations
- **Tool**: Alembic for schema versioning
- **Location**: `/migrations/versions/`
- **Recent**: Added CASCADE delete constraints for foreign key safety

### Schema Evolution Strategy
- Backward-compatible changes when possible
- JSON fields provide flexibility for new features
- Migration scripts handle data transformations
- Rollback procedures for critical changes

### Environment Considerations
- **Development**: SQLite supported for rapid prototyping
- **Production**: PostgreSQL for JSON support and performance
- **Testing**: In-memory SQLite for unit tests

---

This database schema provides a robust foundation for investment research workflow management, combining structured research processes with flexible learning and analytics capabilities. The design emphasizes data integrity, performance, and extensibility while supporting complex investment decision-making workflows.