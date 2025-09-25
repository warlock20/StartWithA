# Database Relationship Diagrams

This document provides visual representations of the key relationships in the Investment Checklist Platform database.

## Core Entity Relationships

### Primary Entity Flow
```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    USER     │───▶│  IDEA_PIPELINE  │───▶│ RESEARCH_PROJECT│───▶│ DECISION_JOURNAL│
│             │    │                 │    │                 │    │                 │
│ - id        │    │ - id            │    │ - id            │    │ - id            │
│ - username  │    │ - name          │    │ - project_name  │    │ - decision_type │
│ - email     │    │ - status        │    │ - status        │    │ - decision_date │
└─────────────┘    │ - thesis_summary│    │ - current_step  │    │ - confidence    │
                   └─────────────────┘    └─────────────────┘    └─────────────────┘
                            │                       │                       │
                            ▼                       ▼                       ▼
                   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                   │  KILL_SESSION   │    │  WORK_SESSION   │    │ INVESTMENT_     │
                   │                 │    │                 │    │ POSTMORTEM      │
                   │ - outcome       │    │ - start_time    │    │                 │
                   │ - time_taken    │    │ - duration      │    │ - actual_return │
                   └─────────────────┘    │ - notes         │    │ - lessons       │
                                          └─────────────────┘    └─────────────────┘
```

### Company-Centric Relationships
```
                            ┌─────────────────┐
                            │    COMPANY      │
                            │                 │
                            │ - id            │
                            │ - name          │
                            │ - ticker_symbol │
                            │ - sector        │
                            └─────────────────┘
                                     │
               ┌─────────────────────┼─────────────────────┐
               │                     │                     │
               ▼                     ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │ FINANCIAL_DATA  │   │COMPANY_DOCUMENT │   │RESEARCH_SESSION │
    │                 │   │                 │   │                 │
    │ - statement_type│   │ - filename      │   │ - start_date    │
    │ - metric_name   │   │ - doc_type      │   │ - status        │
    │ - period_date   │   │ - uploaded_at   │   │ - conclusion    │
    │ - value         │   └─────────────────┘   └─────────────────┘
    └─────────────────┘            │                       │
                                   ▼                       ▼
                         ┌─────────────────┐    ┌─────────────────┐
                         │DOCUMENT_IMPORT  │    │RESEARCH_ANSWER  │
                         │                 │    │                 │
                         │ - processing_   │    │ - answer_text   │
                         │   status        │    │ - satisfaction_ │
                         │ - extracted_    │    │   status        │
                         │   content       │    └─────────────────┘
                         └─────────────────┘
```

### Research System Hierarchy
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│RESEARCH_TEMPLATE│───▶│RESEARCH_PROJECT │───▶│  WORK_SESSION   │
│                 │    │                 │    │                 │
│ - name          │    │ - template_id   │    │ - project_id    │
│ - workflow_steps│    │ - current_step  │    │ - step_index    │
│ - times_used    │    │ - step_notes    │    │ - start_time    │
└─────────────────┘    │ - progress_%    │    │ - findings      │
         │              └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ TEMPLATE_STEP   │    │ RESEARCH_LOG    │
│                 │    │                 │
│ - name          │    │ - activity_type │
│ - step_type     │    │ - timestamp     │
│ - config        │    │ - duration      │
│ - estimated_min │    │ - details       │
└─────────────────┘    └─────────────────┘
```

## Detailed Relationship Types

### One-to-Many Relationships

#### User → Multiple Entities
```
USER (1) ──┬── IDEA_PIPELINE (many)
           ├── RESEARCH_PROJECT (many)
           ├── CHECKLIST (many)
           ├── RESEARCH_SESSION (many)
           ├── COMPANY (many)
           ├── JOURNAL_ENTRY (many)
           ├── MISTAKE_LOG (many)
           └── RESEARCH_METRICS (1)
```

#### Company → Related Data
```
COMPANY (1) ──┬── FINANCIAL_DATA (many)
              ├── COMPANY_DOCUMENT (many)
              ├── RESEARCH_SESSION (many)
              ├── RESEARCH_PROJECT (many)
              ├── DESTINATION_CHECKPOINT (many)
              ├── QUALITATIVE_ANALYSIS (many)
              └── DECISION_JOURNAL (many)
```

#### Research Project → Tracking
```
RESEARCH_PROJECT (1) ──┬── WORK_SESSION (many)
                       ├── RESEARCH_LOG (many)
                       └── INVESTMENT_POSTMORTEM (1)
```

### Many-to-Many Relationships

#### User ↔ Company (Favorites)
```
┌─────────────┐    ┌─────────────────────┐    ┌─────────────┐
│    USER     │◄──►│ FAVORITE_COMPANIES  │◄──►│  COMPANY    │
│             │    │                     │    │             │
│ - id        │    │ - user_id (FK)      │    │ - id        │
│ - username  │    │ - company_id (FK)   │    │ - name      │
└─────────────┘    └─────────────────────┘    └─────────────┘
```

#### Company ↔ Company (Competitors)
```
┌─────────────┐    ┌─────────────────────────┐    ┌─────────────┐
│  COMPANY    │◄──►│COMPETITORS_ASSOCIATION  │◄──►│  COMPANY    │
│             │    │                         │    │             │
│ - id        │    │ - company_id (FK)       │    │ - id        │
│ - name      │    │ - competitor_id (FK)    │    │ - name      │
└─────────────┘    └─────────────────────────┘    └─────────────┘
```

### Self-Referential Relationships

#### Checklist Item Hierarchy
```
┌─────────────────┐
│ CHECKLIST_ITEM  │──┐
│                 │  │
│ - id            │  │ Self-Reference
│ - text          │  │ (parent_id)
│ - parent_id ────┼──┘
│ - order         │
└─────────────────┘
```

## Critical Foreign Key Constraints

### CASCADE Delete Relationships
These relationships automatically delete child records when parent is deleted:

```
USER                    RESEARCH_LOG
 │                        │
 └──── CASCADE ──────────►└─ idea_id (FK)
                           └─ project_id (FK)

IDEA_PIPELINE           RESEARCH_LOG
 │                        │
 └──── CASCADE ──────────►└─ idea_id (FK)

RESEARCH_PROJECT        RESEARCH_LOG
 │                        │
 └──── CASCADE ──────────►└─ project_id (FK)
```

**Critical Note**: These CASCADE relationships were added to prevent foreign key violations during project/idea deletion.

### Standard Foreign Keys (RESTRICT)
These maintain referential integrity without automatic deletion:

```
RESEARCH_SESSION ──┬── user_id → USER
                   ├── company_id → COMPANY
                   └── checklist_id → CHECKLIST

RESEARCH_ANSWER ────┬── research_session_id → RESEARCH_SESSION
                    └── checklist_item_id → CHECKLIST_ITEM

FINANCIAL_DATA ──────── company_id → COMPANY
```

## Data Flow Patterns

### Idea to Investment Flow
```
1. IDEA_PIPELINE (created)
   ├── source analysis
   └── initial screening

2. KILL_SESSION (screening)
   ├── KILL_ANSWER (responses)
   └── outcome (killed/survived)

3. RESEARCH_PROJECT (if promoted)
   ├── WORK_SESSION (research activities)
   ├── RESEARCH_LOG (activity tracking)
   └── progress tracking

4. DECISION_JOURNAL (decision made)
   └── INVESTMENT_POSTMORTEM (outcome analysis)
```

### Research Session Flow
```
1. RESEARCH_SESSION (started)
   └── CHECKLIST (selected)
       └── CHECKLIST_ITEM (questions)

2. RESEARCH_ANSWER (responses)
   ├── satisfaction_status
   └── notes

3. RESEARCH_LOG (activity tracking)
   └── behavioral analytics

4. RESEARCH_METRICS (aggregated)
   └── performance analysis
```

### Learning and Analytics Flow
```
Research Activities
       │
       ▼
┌─────────────────┐
│ RESEARCH_LOG    │──┐
│ (detailed log)  │  │
└─────────────────┘  │
                     │    Aggregation
┌─────────────────┐  │       │
│ MISTAKE_LOG     │──┼───────▼
│ (error tracking)│  │ ┌─────────────────┐
└─────────────────┘  │ │RESEARCH_METRICS │
                     │ │ (performance)   │
┌─────────────────┐  │ └─────────────────┘
│ DECISION_JOURNAL│──┘
│ (decisions)     │
└─────────────────┘
```

## Index Strategy

### Primary Indexes (Performance Critical)
```
- timestamp fields (created_at, updated_at, timestamp)
- status fields (status, is_active, is_public)
- lookup fields (ticker_symbol, sector, activity_type)
- foreign key fields (automatic)
```

### Composite Indexes
```
- (company_id, metric_name, period_date) - Financial data queries
- (user_id, timestamp) - Activity timeline queries
- (day_of_week, hour_of_day) - Behavioral pattern analysis
```

## Database Constraints Summary

### Unique Constraints
- `user.username`, `user.email` - User uniqueness
- `company_document.stored_filename` - File system integrity
- `company_article.url` - Prevent duplicate articles
- `(financial_data.company_id, metric_name, period_date)` - Prevent duplicate metrics
- `research_metrics.user_id` - One metrics record per user

### Check Constraints (Application Level)
- Decision confidence: 1-10 scale
- Satisfaction status: defined enum values
- Status transitions: business logic validation
- Date logic: end_date >= start_date

### NOT NULL Constraints
- All foreign key fields
- Essential business fields (name, email, etc.)
- Timestamp fields for audit trail

This relationship structure provides a comprehensive foundation for investment research workflow management while maintaining data integrity and supporting complex analytical queries.