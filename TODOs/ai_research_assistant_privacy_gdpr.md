# AI Research Assistant - Privacy & GDPR Compliance TODO

**Last Updated:** 2026-01-17
**Status:** Development - Privacy features NOT yet implemented
**Priority:** HIGH - Must be completed before production launch in EU

---

## Overview

The AI Research Assistant collects user data (questions, answers, AI responses) for:
1. **Quality improvement** - Tune prompts based on feedback
2. **Argos correlation** - Link research quality to investment outcomes
3. **Personalized insights** - Identify user-specific blind spots

**Key Constraint:** Argos CANNOT work without user data. We need to correlate research sessions with portfolio outcomes.

---

## GDPR Compliance Requirements

### User Rights to Implement:

**1. Right to Access**
- [ ] User can view all their AI interaction history
- [ ] Create endpoint: `GET /api/user/ai-interactions`
- [ ] UI page showing all interactions with filters (date, mode, feedback)

**2. Right to Deletion**
- [ ] User can request complete data deletion
- [ ] Create endpoint: `DELETE /api/user/ai-interactions`
- [ ] Hard delete all `AIResearchFeedback` records for user
- [ ] Show confirmation: "Deleting this data will disable Argos personalized insights"

**3. Right to Export**
- [ ] User can export their interaction data
- [ ] Create endpoint: `GET /api/user/ai-interactions/export`
- [ ] Format: JSON or CSV download
- [ ] Include: timestamps, questions, answers, AI responses, feedback

**4. Data Retention & Anonymization**
- [ ] Automated cleanup job runs daily
- [ ] After 90 days: Anonymize user_id, analysis_id, item_id, company_name
- [ ] Keep: mode, feedback, tokens_used (aggregated metrics)
- [ ] Set `anonymized_at` timestamp
- [ ] Notify user before anonymization (optional)

**5. Purpose Limitation**
- [ ] Document data usage clearly: "Used ONLY for prompt improvement and Argos insights"
- [ ] Do NOT use for marketing, advertising, or other purposes
- [ ] Privacy policy page explaining data collection

---

## Consent Flow Implementation

### Phase 1: First-Time Use Consent Modal

**Trigger:** User clicks any AI Research Assistant button (Challenge, Elaboration, Fact-Check)

**Modal Content:**
```
┌─────────────────────────────────────────────┐
│  AI Research Assistant - Data Collection    │
├─────────────────────────────────────────────┤
│                                             │
│  To provide AI-powered research assistance  │
│  and personalized insights, we collect:     │
│                                             │
│  • Your research questions and answers      │
│  • AI-generated responses                   │
│  • Your feedback (helpful/not helpful)      │
│                                             │
│  This data is used to:                      │
│  ✓ Improve AI response quality             │
│  ✓ Provide personalized Argos insights     │
│                                             │
│  Your data is:                              │
│  • Stored securely                          │
│  • Anonymized after 90 days                 │
│  • Deletable anytime in settings            │
│                                             │
│  [Learn More] [Privacy Policy]              │
│                                             │
│  [ Decline ]          [ Accept & Continue ] │
└─────────────────────────────────────────────┘
```

**Implementation:**
- [ ] Create modal component (`ai_consent_modal.html`)
- [ ] Add user setting: `ai_assistant_consent` (boolean, default: NULL)
- [ ] On "Accept": Set `user.ai_assistant_consent = True`, proceed with AI request
- [ ] On "Decline": Set `user.ai_assistant_consent = False`, disable AI features
- [ ] Show modal only once (check `ai_assistant_consent IS NULL`)

---

### Phase 2: User Settings Toggle

**Location:** User Settings / Privacy & Data page

**UI Element:**
```
┌─────────────────────────────────────────────┐
│  AI Research Assistant                       │
├─────────────────────────────────────────────┤
│                                             │
│  [✓] Enable AI Research Assistant           │
│                                             │
│  Provides AI-powered challenges and         │
│  suggestions to strengthen your research.   │
│                                             │
│  ⚠️ Disabling will:                         │
│  • Remove AI features from research pages   │
│  • Keep existing data (delete separately)   │
│  • Disable future Argos personalization     │
│                                             │
│  [ View My AI Interaction History ]         │
│  [ Export My Data ]                         │
│  [ Delete All My AI Data ]                  │
│                                             │
└─────────────────────────────────────────────┘
```

**Implementation:**
- [ ] Add toggle in user settings page
- [ ] Update `user.ai_assistant_consent` when toggled
- [ ] Show warning when disabling (impacts Argos)
- [ ] Hide AI features if consent = False

---

### Phase 3: Privacy Policy Page

**Content Required:**
- [ ] What data we collect (questions, answers, AI responses, feedback)
- [ ] Why we collect it (quality improvement, Argos insights)
- [ ] How long we keep it (90 days full data, then anonymized)
- [ ] Who has access (only platform for quality improvement)
- [ ] How to delete/export data
- [ ] User rights (GDPR compliance)

**Implementation:**
- [ ] Create `/privacy/ai-assistant` page
- [ ] Link from consent modal and settings
- [ ] Legal review (consult legal team for EU compliance)

---

## Data Retention Implementation

### Automated Cleanup Job

**Frequency:** Daily (runs at 2 AM UTC)

**Logic:**
```python
def anonymize_old_ai_feedback():
    """
    Anonymize AI feedback data older than 90 days.
    Keeps aggregated metrics, removes user-identifiable data.
    """
    cutoff_date = now_utc() - timedelta(days=90)

    old_records = AIResearchFeedback.query.filter(
        AIResearchFeedback.created_at < cutoff_date,
        AIResearchFeedback.user_id.isnot(None),  # Not already anonymized
        AIResearchFeedback.anonymized_at.is_(None)
    ).all()

    for record in old_records:
        # Remove user-identifiable data
        record.user_id = None
        record.analysis_id = None
        record.item_id = None
        record.company_name = None
        record.anonymized_at = now_utc()

        # Keep: mode, feedback, tokens_used (for metrics)

    db.session.commit()
    logger.info(f"Anonymized {len(old_records)} AI feedback records")
```

**Implementation:**
- [ ] Create Celery task: `anonymize_old_ai_feedback`
- [ ] Schedule via Celery beat (daily at 2 AM UTC)
- [ ] Add logging and monitoring
- [ ] Test with sample data

---

## API Endpoints to Build

### 1. View AI Interaction History
```
GET /api/user/ai-interactions
Query params: ?mode=challenge&feedback=helpful&limit=50&offset=0

Response:
{
  "total": 156,
  "interactions": [
    {
      "id": 123,
      "mode": "challenge",
      "question_text": "What is the moat?",
      "user_answer": "Network effects...",
      "ai_response": "Counter-argument: ...",
      "feedback": "helpful",
      "created_at": "2026-01-15T10:30:00Z",
      "tokens_used": 245
    },
    ...
  ]
}
```

### 2. Export AI Interaction Data
```
GET /api/user/ai-interactions/export?format=json
or
GET /api/user/ai-interactions/export?format=csv

Response: File download
```

### 3. Delete AI Interaction Data
```
DELETE /api/user/ai-interactions
Body: {"confirm": "DELETE_ALL_MY_DATA"}

Response:
{
  "success": true,
  "deleted_count": 156,
  "message": "All AI interaction data deleted. Argos personalization disabled."
}
```

**Implementation:**
- [ ] Create routes in `/app/api/ai_interactions.py` (new blueprint)
- [ ] Add authorization checks (user can only access their own data)
- [ ] Add rate limiting (prevent abuse)
- [ ] Add audit logging (track deletions for compliance)

---

## User Notification System

### When to Notify:

**1. Data Approaching Anonymization (80 days old)**
- [ ] Email: "Your AI interaction data will be anonymized in 10 days"
- [ ] Give option to export before anonymization
- [ ] Optional feature - can be disabled

**2. After Data Deletion**
- [ ] Confirmation email: "Your AI interaction data has been deleted"
- [ ] Remind user: Argos personalization now disabled

**Implementation:**
- [ ] Add to existing email notification system
- [ ] Template: `emails/ai_data_anonymization_reminder.html`
- [ ] Template: `emails/ai_data_deleted_confirmation.html`

---

## Database Schema Updates (Future)

### Add User Consent Field

```python
class User(db.Model):
    # Existing fields...

    # AI Research Assistant consent
    ai_assistant_consent = db.Column(db.Boolean, nullable=True, default=None)
    # NULL = not asked yet, True = consented, False = declined

    ai_assistant_consent_date = db.Column(db.DateTime, nullable=True)
    # When user provided consent
```

**Migration:**
- [ ] Create migration adding `ai_assistant_consent` fields to User model
- [ ] Default existing users to NULL (prompt on next AI feature use)

---

## Testing & Validation

### Manual Testing Checklist:
- [ ] Consent modal appears on first AI feature use
- [ ] Consent modal does NOT appear on subsequent uses
- [ ] AI features disabled when consent = False
- [ ] User can toggle consent in settings
- [ ] Data export downloads all user's AI interactions
- [ ] Data deletion removes all user's records
- [ ] Anonymization job runs correctly (test in staging)
- [ ] Anonymized records no longer show user_id

### Automated Tests:
- [ ] Unit tests for anonymization logic
- [ ] Integration tests for API endpoints
- [ ] Test GDPR deletion cascade (delete user → delete AI feedback)

---

## Compliance Checklist (Before Production)

**Legal:**
- [ ] Privacy policy reviewed by legal team
- [ ] Consent flow reviewed by legal team
- [ ] Data retention policy approved
- [ ] GDPR compliance verified

**Technical:**
- [ ] All API endpoints implemented
- [ ] Anonymization job running in production
- [ ] Monitoring and alerting configured
- [ ] Backup/restore tested

**User Experience:**
- [ ] Consent modal tested with users
- [ ] Settings page tested
- [ ] Data export tested
- [ ] Privacy policy clear and understandable

---

## Cost & Performance Considerations

**Storage Estimation:**
- Average interaction: ~2 KB (question + answer + AI response)
- 100 users × 10 interactions/user/month = 1,000 interactions/month
- Monthly storage: ~2 MB
- After 90 days anonymization: ~500 bytes/record (just metrics)

**Database Optimization:**
- [ ] Add composite index: (user_id, created_at) for user history queries
- [ ] Add index: (created_at, anonymized_at) for cleanup job
- [ ] Monitor query performance with EXPLAIN

---

## Implementation Priority

### Phase 1 (MVP - Low Risk Development):
✅ Build AI features without consent flow
✅ Store data (development environment only)
✅ Test functionality and prompt quality

### Phase 2 (Pre-Production - HIGH PRIORITY):
- [ ] Implement consent modal
- [ ] Add user settings toggle
- [ ] Build API endpoints (view, export, delete)
- [ ] Create privacy policy page
- [ ] Legal review

### Phase 3 (Production):
- [ ] Deploy with consent flow enabled
- [ ] Enable anonymization job
- [ ] Monitor compliance
- [ ] User support documentation

### Phase 4 (Post-Launch):
- [ ] Add email notifications (optional)
- [ ] Enhance export formats
- [ ] Add audit logging
- [ ] Quarterly compliance review

---

## Notes

- **Development Environment:** Privacy features not enforced (testing only)
- **Staging Environment:** Test consent flow before production
- **Production Environment:** ALL privacy features MUST be active
- **EU Users:** Stricter GDPR enforcement, prioritize compliance
- **Non-EU Users:** Still apply best practices for user trust

---

## Resources

- GDPR Official Text: https://gdpr-info.eu/
- Right to Deletion (Article 17): https://gdpr-info.eu/art-17-gdpr/
- Right to Data Portability (Article 20): https://gdpr-info.eu/art-20-gdpr/
- ICO Guidance (UK): https://ico.org.uk/for-organisations/guide-to-data-protection/

---

## Contact

For questions about AI Research Assistant privacy implementation:
- Review this document
- Consult legal team for compliance questions
- Update this document as requirements evolve
