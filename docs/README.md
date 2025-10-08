# Investment Checklist Platform - Documentation

## Overview

This documentation provides comprehensive information about the Investment Checklist Platform, a sophisticated investment research and decision-making system built with Flask, PostgreSQL, and modern web technologies.

## Documentation Structure

### 📊 Database Documentation
- **[Database Schema](database_schema.md)** - Complete database structure with all 32 tables and their specifications
- **[Database Relationships](database_relationships.md)** - Visual relationship diagrams and foreign key structures
- **[Database Usage Patterns](database_usage_patterns.md)** - Common queries, data flows, and optimization strategies

### 🔄 System Documentation
- **[Research Workflow](research_workflow.md)** - Advanced research workflow system with templates and projects
- **[Idea Pipeline System](idea_pipeline_system.md)** - Idea management and screening workflows
- **[Checklist System](checklist_system.md)** - Traditional research checklist functionality

## Quick Reference

### Database Overview
- **32 Main Tables** + 2 Association Tables
- **PostgreSQL** with JSON support for flexible data structures
- **SQLAlchemy ORM** with Flask-SQLAlchemy integration
- **Alembic migrations** for schema versioning

### Key Table Categories

| Category | Tables | Purpose |
|----------|--------|---------|
| **User Management** | `user`, `favorite_companies` | Authentication and user preferences |
| **Company Data** | `company`, `financial_data`, `company_document`, `company_article` | Company information and market data |
| **Research Tools** | `checklist`, `research_session`, `research_answer` | Traditional research checklists |
| **Idea Pipeline** | `idea_pipeline`, `kill_checklist`, `kill_session` | Idea screening and management |
| **Advanced Workflow** | `research_template`, `research_project`, `work_session` | Template-based research processes |
| **Decision Tracking** | `decision_journal`, `investment_postmortem` | Investment decisions and outcomes |
| **Learning System** | `learning_note`, `mistake_log`, `pattern_recognition` | Continuous improvement and learning |
| **Analytics** | `research_metrics`, `research_log` | Performance tracking and behavioral analysis |

### Core Workflows

1. **Idea to Investment Flow**
   ```
   Idea Capture → Kill Screening → Research Project → Decision → Post-mortem
   ```

2. **Research Session Flow**
   ```
   Checklist Selection → Question Answering → Analysis → Conclusion
   ```

3. **Template-Based Research**
   ```
   Template Selection → Step Execution → Progress Tracking → Completion
   ```

### Critical Design Patterns

#### CASCADE Delete Relationships ⚠️
```sql
-- These relationships automatically delete child records
research_log.idea_id → idea_pipeline.id (CASCADE)
research_log.project_id → research_project.id (CASCADE)
```

#### JSON Data Structures
- **Workflow Steps**: Flexible template definitions
- **Research Results**: Structured findings and analysis
- **User Metrics**: Aggregated performance data

#### Performance Optimizations
- Strategic indexing on timestamps and status fields
- Materialized views for dashboard queries
- Denormalized metrics tables for analytics

## Getting Started

### For Developers
1. Review the [Database Schema](database_schema.md) to understand the data model
2. Study [Database Relationships](database_relationships.md) for foreign key constraints
3. Check [Database Usage Patterns](database_usage_patterns.md) for common query patterns

### For System Administrators
1. Understand the database structure from [Database Schema](database_schema.md)
2. Review performance optimization strategies in [Database Usage Patterns](database_usage_patterns.md)
3. Study the migration patterns for schema evolution

### For Business Users
1. Read [Research Workflow](research_workflow.md) to understand advanced research capabilities
2. Review [Idea Pipeline System](idea_pipeline_system.md) for idea management workflows
3. Check [Checklist System](checklist_system.md) for traditional research tools

## Database Statistics

### Table Count by Category
- **Core Entities**: 8 tables (User, Company, Projects, etc.)
- **Research Tools**: 6 tables (Checklists, Sessions, Answers)
- **Idea Management**: 5 tables (Pipeline, Kill Checklists, Sessions)
- **Advanced Workflow**: 4 tables (Templates, Projects, Work Sessions)
- **Learning & Analytics**: 9 tables (Metrics, Logs, Learning Notes)

### Key Relationships
- **One-to-Many**: 25+ relationships (User → Projects, Company → Documents, etc.)
- **Many-to-Many**: 2 relationships (User ↔ Company favorites, Company ↔ Competitors)
- **Self-Referential**: 2 relationships (Checklist item hierarchy, Company competitors)

### Performance Features
- **Indexes**: 20+ strategic indexes for query optimization
- **Constraints**: 15+ unique constraints for data integrity
- **JSON Fields**: 10+ JSON columns for flexible data storage

## Migration History

### Recent Changes
- **2024-09**: Added CASCADE delete constraints for foreign key safety
- **2024-09**: Enhanced research workflow with rich note-taking
- **2024-09**: Improved database documentation and relationship mapping

### Schema Evolution Strategy
- JSON fields provide flexibility for new features
- Backward-compatible migrations when possible
- Comprehensive rollback procedures for critical changes

## Performance Guidelines

### Query Best Practices
- Use indexes on timestamp and status fields
- Leverage JSON operators for flexible queries
- Consider materialized views for complex analytics

### Data Integrity
- Foreign key constraints maintain referential integrity
- CASCADE deletes prevent orphaned records
- Unique constraints prevent data duplication

### Monitoring Points
- Query performance on large datasets
- Index usage and optimization
- JSON field query patterns
- Migration execution time

## Support and Maintenance

### Regular Maintenance Tasks
- **Daily**: Monitor query performance and errors
- **Weekly**: Review new user activity and data growth
- **Monthly**: Analyze database performance metrics
- **Quarterly**: Plan schema improvements and optimizations

### Backup Strategy
- **Full Backups**: Daily for production data
- **Incremental**: Hourly for active research data
- **Point-in-Time Recovery**: For critical data restoration
- **Testing**: Regular restoration testing

### Scaling Considerations
- Read replicas for analytics workloads
- Connection pooling for high concurrency
- Data archiving for historical records
- Query optimization for large datasets

---

## Document Versions

| Document | Last Updated | Version |
|----------|-------------|---------|
| Database Schema | 2024-09-24 | 1.0 |
| Database Relationships | 2024-09-24 | 1.0 |
| Database Usage Patterns | 2024-09-24 | 1.0 |

This documentation is maintained alongside the codebase and should be updated with any schema changes or new features.