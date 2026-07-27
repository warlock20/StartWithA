# 🗄️ Database Schema Updates for User Journey Features

## Overview
This document outlines the database schema changes needed to support the new User Journey features:
1. Guided First Ten Minutes Onboarding
2. Research Sprint Mode
3. Pattern Recognition Alerts
4. Investment Buddy System
5. Anti-FOMO Circuit Breaker

## 📋 Schema Updates Required

### 1. User Model Enhancements (Onboarding & Preferences)

Add the following fields to the existing `User` model:

```python
# Onboarding tracking
onboarding_completed = db.Column(db.Boolean, default=False)
onboarding_step = db.Column(db.Integer, default=0)  # Track current step (0-5)
onboarding_started_at = db.Column(db.DateTime)
onboarding_completed_at = db.Column(db.DateTime)

# User preferences
preferred_sprint_duration = db.Column(db.Integer, default=30)  # minutes
research_experience_level = db.Column(db.String(20), default='intermediate')  # beginner, intermediate, expert
notification_preferences = db.Column(db.JSON, default={'pattern_alerts': True, 'weekly_review': True, 'fomo_alerts': True})

# Community features
buddy_system_enabled = db.Column(db.Boolean, default=False)
peer_feedback_count = db.Column(db.Integer, default=0)
community_reputation = db.Column(db.Integer, default=0)

# FOMO protection
last_fomo_alert = db.Column(db.DateTime)
fomo_protection_level = db.Column(db.String(20), default='medium')  # low, medium, high
```

### 2. New Model: OnboardingProgress

Track detailed onboarding progress and user's first experience:

```python
class OnboardingProgress(db.Model):
    __tablename__ = 'onboarding_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Step tracking
    current_step = db.Column(db.Integer, default=0)
    completed_steps = db.Column(db.JSON, default=[])  # List of completed step numbers

    # First experience data
    first_company_name = db.Column(db.String(200))  # Their first company idea
    first_company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    first_kill_checklist_id = db.Column(db.Integer, db.ForeignKey('kill_checklist.id'))
    first_research_template_id = db.Column(db.Integer, db.ForeignKey('research_template.id'))

    # Timing
    step_start_times = db.Column(db.JSON, default={})  # Track time spent on each step
    step_completion_times = db.Column(db.JSON, default={})

    # Feedback
    onboarding_feedback = db.Column(db.Text)
    satisfaction_score = db.Column(db.Integer)  # 1-10

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='onboarding_progress')
    first_company = db.relationship('Company', foreign_keys=[first_company_id])
    first_kill_checklist = db.relationship('KillChecklist', foreign_keys=[first_kill_checklist_id])
    first_research_template = db.relationship('ResearchTemplate', foreign_keys=[first_research_template_id])
```

### 3. New Model: ResearchSprint

Track time-boxed research sessions:

```python
class ResearchSprint(db.Model):
    __tablename__ = 'research_sprint'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Sprint details
    duration_planned = db.Column(db.Integer, nullable=False)  # minutes
    duration_actual = db.Column(db.Integer)  # actual time spent

    # Sprint content
    sprint_type = db.Column(db.String(50))  # 'quick_task', 'focused_research', 'checklist_items'
    task_description = db.Column(db.Text)
    target_project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'))
    target_checklist_items = db.Column(db.JSON)  # List of checklist item IDs

    # Sprint status
    status = db.Column(db.String(20), default='planned')  # planned, active, completed
    completion_percentage = db.Column(db.Integer, default=0)

    # Results
    tasks_completed = db.Column(db.Integer, default=0)
    insights_gained = db.Column(db.Text)
    next_steps_identified = db.Column(db.Text)
    satisfaction_score = db.Column(db.Integer)  # 1-10

    # Timing
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='research_sprints')
    target_project = db.relationship('ResearchProject', foreign_keys=[target_project_id])
```

### 4. Enhanced Model: PatternRecognition Updates

Add new fields to existing PatternRecognition model for better alerts:

```python
# Add these fields to existing PatternRecognition model:

# Alert system
alert_enabled = db.Column(db.Boolean, default=True)
alert_threshold = db.Column(db.Integer, default=3)  # Trigger alert after N occurrences
last_alert_sent = db.Column(db.DateTime)
alert_frequency = db.Column(db.String(20), default='immediate')  # immediate, daily, weekly

# Pattern source tracking
pattern_source = db.Column(db.String(50))  # 'kill_checklist', 'mistake_log', 'research_behavior'
related_kill_criteria = db.Column(db.JSON)  # List of kill criterion IDs related to this pattern
related_mistakes = db.Column(db.JSON)  # List of mistake log IDs

# User interaction
user_acknowledged = db.Column(db.Boolean, default=False)
user_feedback = db.Column(db.Text)
action_taken = db.Column(db.Text)  # What user did in response to pattern
```

### 5. New Model: PeerFeedback (Investment Buddy System)

```python
class PeerFeedback(db.Model):
    __tablename__ = 'peer_feedback'

    id = db.Column(db.Integer, primary_key=True)

    # Participants
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Content being reviewed
    content_type = db.Column(db.String(50))  # 'thesis', 'research_project', 'kill_decision'
    content_id = db.Column(db.Integer)  # ID of the content being reviewed
    sanitized_content = db.Column(db.JSON)  # Anonymized version for peer review

    # Feedback
    feedback_text = db.Column(db.Text)
    feedback_score = db.Column(db.Integer)  # 1-10 quality rating
    feedback_categories = db.Column(db.JSON)  # ['strengths', 'weaknesses', 'blind_spots', 'suggestions']

    # Review process
    status = db.Column(db.String(20), default='requested')  # requested, in_progress, completed, declined
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Quality tracking
    helpful_rating = db.Column(db.Integer)  # 1-5, rated by requester
    reviewer_expertise_level = db.Column(db.String(20))  # Reviewer's experience in this sector

    # Relationships
    requester = db.relationship('User', foreign_keys=[requester_id], backref='feedback_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='feedback_given')
```

### 6. New Model: MarketConditionAlert (Anti-FOMO Circuit Breaker)

```python
class MarketConditionAlert(db.Model):
    __tablename__ = 'market_condition_alert'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Market conditions
    market_condition = db.Column(db.String(50))  # 'euphoria', 'fear', 'volatility', 'normal'
    trigger_indicators = db.Column(db.JSON)  # List of indicators that triggered alert
    vix_level = db.Column(db.Float)
    market_cap_to_gdp = db.Column(db.Float)

    # Alert details
    alert_type = db.Column(db.String(50))  # 'fomo_warning', 'volatility_alert', 'process_reminder'
    alert_message = db.Column(db.Text)
    severity_level = db.Column(db.String(20))  # 'low', 'medium', 'high'

    # User response
    user_acknowledged = db.Column(db.Boolean, default=False)
    user_action = db.Column(db.String(100))  # 'proceeded_carefully', 'delayed_decision', 'ignored'
    action_notes = db.Column(db.Text)

    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='market_alerts')
```

### 7. New Model: WeeklyReviewAnalytics

Enhance existing WeeklyReview with analytics:

```python
class WeeklyReviewAnalytics(db.Model):
    __tablename__ = 'weekly_review_analytics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    week_ending = db.Column(db.Date, nullable=False)

    # Activity metrics
    ideas_captured = db.Column(db.Integer, default=0)
    ideas_killed = db.Column(db.Integer, default=0)
    research_sessions_worked = db.Column(db.Integer, default=0)
    mistakes_logged = db.Column(db.Integer, default=0)
    patterns_identified = db.Column(db.Integer, default=0)

    # Time metrics
    total_research_time = db.Column(db.Integer, default=0)  # minutes
    average_session_length = db.Column(db.Integer, default=0)  # minutes
    sprints_completed = db.Column(db.Integer, default=0)

    # Quality metrics
    process_adherence_score = db.Column(db.Float)  # 0-10
    decision_quality_score = db.Column(db.Float)  # 0-10
    learning_velocity = db.Column(db.Float)  # Rate of improvement

    # Insights
    key_insights = db.Column(db.JSON)  # List of key insights from journal entries
    improvement_areas = db.Column(db.JSON)  # Identified areas for improvement
    success_patterns = db.Column(db.JSON)  # Successful patterns identified

    # Reflections
    biggest_insight = db.Column(db.Text)
    process_feedback = db.Column(db.Text)
    next_week_priority = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='weekly_analytics')
```

## 🔧 Migration Plan

### Step 1: Create Migration Files
1. Create migration for User model updates
2. Create migration for new OnboardingProgress model
3. Create migration for ResearchSprint model
4. Create migration for PatternRecognition updates
5. Create migration for PeerFeedback model
6. Create migration for MarketConditionAlert model
7. Create migration for WeeklyReviewAnalytics model

### Step 2: Default Data Population
- Add default notification preferences for existing users
- Initialize onboarding_completed = True for existing users
- Set up default market condition monitoring

### Step 3: Index Creation
```sql
-- Performance indexes
CREATE INDEX idx_user_onboarding ON user(onboarding_completed, onboarding_step);
CREATE INDEX idx_pattern_alerts ON pattern_recognition(alert_enabled, last_alert_sent);
CREATE INDEX idx_sprint_status ON research_sprint(user_id, status, created_at);
CREATE INDEX idx_market_alerts ON market_condition_alert(user_id, created_at);
CREATE INDEX idx_weekly_analytics ON weekly_review_analytics(user_id, week_ending);
```

## ✅ Implementation Checklist

- [ ] Create migration files for all new models
- [ ] Update User model with new fields
- [ ] Enhance PatternRecognition model
- [ ] Create OnboardingProgress model
- [ ] Create ResearchSprint model
- [ ] Create PeerFeedback model
- [ ] Create MarketConditionAlert model
- [ ] Create WeeklyReviewAnalytics model
- [ ] Add database indexes for performance
- [ ] Create default data population scripts
- [ ] Test all migrations in development
- [ ] Update model relationships and foreign keys
- [ ] Create API endpoints for new functionality

## 🎯 Next Steps

1. Review and approve this schema design
2. Begin implementing migrations step by step
3. Create wireframes for onboarding flow
4. Plan user journey mapping for each feature

This schema provides the foundation for all our planned User Journey features while maintaining data integrity and performance.