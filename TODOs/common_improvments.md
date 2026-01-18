# Platform Level Improvements

**Last Updated:** 2026-01-18

---

## 🚨 CRITICAL - Beta Blocking (Priority 0)

### 1. AI Token Usage Monitoring & Limits ✅ COMPLETE
**Why Critical:** Prevent unlimited AI costs, protect platform sustainability

- ✅ Add token tracking columns to User model (monthly usage, limit, reset date)
- ✅ Create middleware/decorator to check token limits before AI calls
- ✅ Implement monthly reset logic (cron job or on-demand check)
- ✅ Track token usage across all AI features (research assistant implemented)
- ✅ Store actual tokens used (not estimates) from AI provider responses
- ✅ Add usage dashboard widget for users (show tokens used / limit)
- ✅ Return user-friendly error when limit exceeded ("AI usage limit reached, resets on X")
- ✅ Admin view to monitor platform-wide token consumption

**Model-Specific Pricing:** Different AI providers/models have different costs - track per model, calculate cost dynamically
**Status:** Token tracking stores provider/model info in AIResearchFeedback table

### 2. Subscription Tier System ⚠️ PARTIAL (Core Complete)
**Why Critical:** Revenue model foundation, control feature access

- ✅ Define tier structure (free, beta_tester, pro) with token limits
- ✅ Add subscription_tier column to User model (already existed)
- ✅ Set default tier for new signups (free)
- ⬜ Implement tier-based feature gates (if needed) - defer to when needed
- ⬜ Create tier upgrade/downgrade workflow - defer to payment integration
- ✅ Add tier badge/indicator in UI
- ✅ Configure tier limits via admin panel (make it easy to adjust)

**Recommended Starting Limits (for tuning):**
- Free: 10,000 tokens/month (~20-30 AI interactions, ~$0.10 cost with Gemini Flash)
- Beta Tester: 50,000 tokens/month (~100-150 interactions, ~$0.50 cost)
- Pro (future): 500,000 tokens/month (~1000+ interactions, ~$5 cost)

**Status:** Core tier system working. Upgrade workflow deferred to payment integration phase.

### 3. Admin Panel Extensions (Flask-Admin) ⚠️ PARTIAL (Core Complete)
**Why Critical:** Manage beta users, monitor usage, adjust limits

- ✅ Add User management view (existing flask-admin extension)
- ✅ Add ability to change user subscription tier from admin panel
- ✅ Add token usage analytics view (platform-wide consumption) - AIResearchFeedbackView
- ✅ Add ability to manually reset user token limits (for exceptions) - editable fields
- ✅ Add AI interaction logs view (for debugging/monitoring) - AIResearchFeedbackView
- ⬜ Add cost tracking dashboard (estimated monthly AI spend) - defer to analytics phase
- ⬜ Add ability to disable AI features platform-wide (emergency kill switch) - defer to production
- ⬜ Add a feedback spinner to "Add a new company" modal

**Status:** Essential admin views complete. Advanced dashboards deferred.

### 4. Error Monitoring & Logging ⚠️ PARTIAL (Logging Complete)
**Why Critical:** Catch bugs during beta, understand failure modes

- ⬜ Set up error tracking (Sentry or similar) for production - TODO before beta launch
- ✅ Add structured logging for all AI interactions (success/failure/tokens)
- ✅ Log rate limiting events (who hit limits, when)
- ⬜ Monitor database performance (slow queries) - defer to if needed
- ⬜ Set up daily/weekly summary emails (errors, usage, costs) - defer to production

**Status:** Application logging complete. External monitoring tools TODO.

---

## ⚠️ IMPORTANT - Pre-Beta Polish (Priority 1)

### 5. Usage Analytics for Decision Making
- Track which AI features are used most (research vs portfolio vs journal)
- Track which AI modes are most popular (challenge vs elaboration vs factcheck)
- Track user feedback patterns (helpful vs not_helpful ratios)
- Identify heavy users vs light users (cohort analysis)
- Calculate actual cost per user per feature

### 6. User Experience Improvements
- ⬜ Add onboarding flow for new beta testers
- ⬜ Add feature introduction tooltips (what is Challenge mode?)
- ✅ Improve error messages across platform (user-friendly, actionable) - 429 error handling done
- ✅ Add loading states for all async operations - AI assistant has loading states
- ⬜ Add success confirmations for important actions
- ⬜ Improve mobile responsiveness (if beta includes mobile users)
- ⬜ Add global notifications system - deferred to post-beta

### 7. Security & Data Protection
- Audit API endpoints for authorization checks (ensure users can't access other users' data)
- Review all database queries for SQL injection risks
- Ensure CSRF protection on all forms
- Add rate limiting to public-facing endpoints (prevent abuse)
- Review file upload security (if applicable)
- Ensure sensitive data is not logged (API keys, passwords, etc.)

### 8. Performance Optimization (If Needed)
- Identify slow database queries (use Flask-DebugToolbar or similar)
- Add database indexes where needed (frequently queried columns)
- Optimize heavy pages (reduce N+1 queries)
- Consider caching for expensive operations (if applicable)
- Test platform under realistic beta load

---

## 📋 NICE TO HAVE - Post-Beta (Priority 2)

### 9. Code Quality Improvements
- Refactor duplicated code (DRY violations identified during development)
- Add type hints to critical functions
- Improve function/variable naming for clarity
- Extract magic numbers to constants/config
- Add docstrings to complex functions
- Remove dead code and unused imports

### 10. Financial Data Abstraction Layer Integration
**Status:** Implemented, BUT need to integrate it across the platform

- Replace direct Yahoo Finance calls with abstraction layer
- Migrate existing features to use unified data fetcher
- Test all financial data fetching after migration
- Add fallback logic if primary provider fails
- Document which features use which data sources

### 11. Utils Library Improvements
- Add missing date utilities to time_utils (date returner functions)
- Standardize datetime handling across platform (UTC vs local time)
- Create common validation utilities (email, phone, etc.)
- Add common formatting utilities (currency, percentages, etc.)
- Document all utility functions with examples

### 12. Testing & Quality Assurance
- Add unit tests for critical business logic
- Add integration tests for key user flows
- Add tests for AI token limiting logic
- Test edge cases (subscription expiry, token limits, etc.)
- Set up CI/CD pipeline for automated testing

### 13. Documentation
- Write beta tester guide (how to use the platform)
- Document all major features (research workflow, portfolio tracking, etc.)
- Create troubleshooting guide (common issues + solutions)
- Document admin panel usage (for managing users)
- Add inline help/tooltips for complex features

---

## 🔮 FUTURE - Long-term Improvements (Priority 3)

### 14. Payment Integration (Post-Beta)
- Integrate Stripe for subscription payments
- Add billing dashboard for users
- Handle subscription lifecycle (signup, renewal, cancellation, refunds)
- Add invoicing and receipts
- Implement proration for mid-cycle upgrades/downgrades

### 15. Advanced Analytics
- Build analytics dashboard for users (research quality metrics, etc.)
- Build admin analytics (user engagement, feature adoption, churn)
- Add cohort analysis (beta users vs paid users)
- Track feature usage over time
- Calculate LTV and CAC metrics

### 16. Platform Scalability
- Consider database optimization for scale (sharding, read replicas, etc.)
- Add Redis caching for frequently accessed data
- Consider CDN for static assets
- Optimize AI calls (batching, caching common responses, etc.)
- Plan for horizontal scaling if user base grows

---

## 📊 Pre-Beta Launch Checklist

**Must Complete Before Beta:**
- [x] Token usage monitoring implemented and tested
- [x] Subscription tiers configured and working
- [x] Admin panel extensions complete (user management, usage monitoring)
- [ ] Error tracking enabled (Sentry or similar) - NEXT PRIORITY
- [ ] Security audit complete (authorization, rate limiting, etc.)
- [ ] Critical bugs fixed (P0 issues)
- [ ] Beta tester documentation written
- [ ] Onboarding flow ready
- [ ] Backup/disaster recovery plan in place

**Can Defer to During/After Beta:**
- [ ] Code refactoring and cleanup
- [ ] Financial data abstraction layer migration
- [ ] Comprehensive test coverage
- [ ] Performance optimization (unless platform is slow)
- [ ] Advanced analytics
- [ ] Payment integration

---

## Notes

**Development Philosophy for Beta:**
- Ship working features over perfect code
- Fix critical bugs immediately, defer refactoring
- Collect user feedback early and often
- Iterate based on real usage patterns
- Monitor costs and usage closely
- Be ready to adjust limits and pricing based on data

**When to Optimize:**
- When something is actually slow (not preemptively)
- When duplication causes bugs (not just aesthetics)
- When technical debt blocks new features
- After beta feedback validates feature value
    