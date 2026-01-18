# Research Workflow - AI Features Roadmap

**Last Updated:** 2026-01-18
**Goal:** Add lightweight AI features to research workflow to improve quality and collect data for Argos
**Philosophy:** Micro-interactions over expensive full-document analysis
**Status:** ✅ Phase 1 MVP COMPLETE - All 3 AI modes working in production

---

## 🎯 Core Strategy

**Approach:** Build focused, cost-effective AI interactions that help users during research while collecting structured data for Argos.

**Key Principles:**
1. **Lightweight over Heavy:** Use targeted prompts (question + answer) instead of uploading entire documents
2. **Verification over Generation:** Challenge/verify user findings rather than doing research for them
3. **Data Collection:** Every AI interaction generates structured feedback → Argos training data
4. **User Agency:** AI assists and challenges, but user remains in control

**Integration Points:**
- **Checklist Items:** AI verification and counter-arguments for user answers
- **Research Notes:** Synthesis and pattern detection across notes
- **Decision Journal:** Thesis consistency checks and bias detection
- **Future:** Connect to portfolio outcomes → "What questions correlated with good trades?"

---

## Phase 1: Devil's Advocate Assistant - Option 4 Enhanced ✅ COMPLETE

### ✅ Design Decisions Made

**UI Approach:** Option 4 Enhanced - Unified AI Assistant
- All AI features grouped in single accordion section
- Visual card grid showing 4 AI modes (Challenge, Elaboration, Fact-Check, Document Analysis)
- Smooth JavaScript interactions (no page reloads)
- Single response area below mode cards
- User settings to enable/disable individual modes

**AI Modes:**
1. **Challenge Mode** (NEW) - Devil's Advocate counter-arguments
2. **Elaboration Mode** (NEW) - Follow-up questions to deepen analysis
3. **Fact-Check Mode** (NEW) - Verify claims and request evidence
4. **Document Analysis** (EXISTING) - Extract insights from uploaded documents

**Technical Decisions:**
- AJAX-based interactions for smooth UX
- YAML prompt templates (like portfolio analytics)
- Gemini Flash for cost-effective inference
- Plain text responses with formatting
- Single-turn interaction (MVP), multi-turn in future
- User feedback tracking (helpful/not helpful)

---

### Implementation Roadmap

### Step 1: Foundation & Infrastructure ✅ COMPLETE

**1.1 Create YAML Prompt Templates**
- [x] Create prompt templates directory structure
- [x] Write Devil's Advocate prompt template (challenge mode)
- [x] Write Elaboration prompt template (follow-up questions)
- [x] Write Fact-Check prompt template (claim verification)
- [x] Test prompts manually with AI service to refine quality
- [x] Define expected response format and structure

**1.2 Backend API Route**
- [x] Create new Flask route for AI challenge endpoint
- [x] Accept parameters: mode, answer_text, question_text, company_name, analysis_id, item_id
- [x] Integrate with existing AI service (use Gemini Flash)
- [x] Load appropriate YAML template based on mode
- [x] Return JSON response with AI-generated content
- [x] Add error handling and rate limiting
- [x] Add logging for debugging and monitoring

**1.3 Database Schema**
- [x] Design table for AI interaction tracking (AIResearchFeedback model)
- [x] Store: user_id, analysis_id, item_id, mode, user_answer, ai_response, user_feedback, timestamp
- [x] Add privacy documentation and GDPR compliance TODO
- [x] Create and apply database migration

---

### Step 2: Frontend UI - Unified AI Assistant Section ✅ COMPLETE

**2.1 Update Template HTML**
- [x] Modify research_step.html template
- [x] Replace existing "Analyze with AI Assistant" accordion
- [x] Add new unified AI assistant accordion section
- [x] Create 4-card grid layout (Challenge, Elaboration, Fact-Check, Document Analysis)
- [x] Add single response area below cards
- [x] Add feedback buttons (Helpful, Not Helpful, Dismiss)
- [x] Document Analysis marked as "Coming Soon" (disabled for now)
- [ ] Add collapsible settings section for enabling/disabling modes (deferred to Phase 1.5)

**2.2 JavaScript Interactions**
- [x] Create reusable JavaScript module (ai-research-assistant.js)
- [x] Implement card click handlers to trigger AI mode
- [x] AJAX call to backend API endpoint
- [x] Show loading spinner during AI processing with mode-specific messages
- [x] Render AI response in response area (plain text with markdown-style formatting)
- [x] Handle errors gracefully with user-friendly messages
- [x] Implement dismiss/close response functionality
- [x] Track which response is currently shown (hide others)
- [x] Proper text extraction from BlockNote editor

**2.3 Feedback Mechanism**
- [x] Implement feedback button handlers (Helpful/Not Helpful/Dismissed)
- [x] Send feedback to backend for tracking
- [x] Feedback stored in database with all context
- [x] Regenerate functionality implemented (backend route ready, UI integration pending)

---

### Step 3: MVP - All Three Modes ✅ COMPLETE

**Decision:** Implemented all 3 modes together since infrastructure was reusable

**3.1 Challenge Mode Implementation**
- [x] Ensure Challenge Mode prompt template is high-quality
- [x] Test prompt with various question types (moat, risks, valuation, etc.)
- [x] Verify response quality and relevance
- [x] Tune response length (set to 5000 max_tokens for detailed responses)
- [x] Test with different company contexts (TFF Group cooperage analysis)
- [x] Fixed Gemini RECITATION filter issues with prompt clarifications

**3.2 Elaboration Mode Implementation**
- [x] Create elaboration prompt template
- [x] Implement follow-up question generation
- [x] Test with real research scenarios
- [x] Set max_tokens to 5000 for comprehensive questions

**3.3 Fact-Check Mode Implementation**
- [x] Create fact-check prompt template
- [x] Implement claim verification prompts
- [x] Test with answers containing specific claims
- [x] Set max_tokens to 5000 for thorough fact-checking

**3.4 Quality Checks & Bug Fixes**
- [x] Fixed provider/model not being passed from YAML to AI service
- [x] Changed default model from gemini-2.5-flash to gemini-flash-latest
- [x] Fixed JavaScript selector bug (querySelector targeting wrong element)
- [x] Fixed max_tokens issue (400 was too low, increased to 5000)
- [x] All three modes tested and working in production

---

### Step 4: Expand to All Modes ✅ COMPLETE (Merged with Step 3)

**4.1 Elaboration Mode**
- [x] Implement elaboration prompt template
- [x] Add follow-up question generation logic
- [x] Test with various question types
- [x] Ensure questions are actionable and specific
- [x] Working in production

**4.2 Fact-Check Mode**
- [x] Implement fact-check prompt template
- [x] Add claim extraction and verification logic
- [x] Test with answers containing specific claims/metrics
- [x] Ensure requests for sources are reasonable
- [x] Working in production

**4.3 Document Analysis Integration**
- [x] Preserve existing document analysis functionality
- [x] Move it into 4th card in grid
- [x] Marked as "Coming Soon" (disabled) to focus on new modes
- [ ] Future: Re-enable and integrate with new AI assistant flow (Phase 1.5)

---

### Step 5: Settings & User Preferences ⏳

**5.1 User Settings UI**
- [ ] Add settings panel in accordion footer
- [ ] Toggles to enable/disable each AI mode
- [ ] Save preferences to user settings table
- [ ] Load preferences on page load
- [ ] Hide disabled modes from card grid

**5.2 Persistence**
- [ ] Store settings in database (user preferences table)
- [ ] Default: All modes enabled for new users
- [ ] Allow per-user customization
- [ ] Consider global admin toggle to disable features

---

### Step 6: Feedback Tracking & Analytics 🔮

**6.1 Feedback Collection**
- [ ] Store feedback in database (helpful/not helpful)
- [ ] Track which modes users find most valuable
- [ ] Monitor response dismissal rate
- [ ] Identify low-quality responses based on feedback

**6.2 Usage Analytics**
- [ ] Track mode usage frequency (which modes used most)
- [ ] Monitor cost per mode
- [ ] Measure impact on answer quality (future: compare revised vs original)
- [ ] Identify which question types benefit most from AI assistance

**6.3 Future Argos Integration**
- [ ] Design schema for correlation analysis
- [ ] Track: Did user revise answer after AI challenge?
- [ ] Future: Correlate challenged answers with trade outcomes
- [ ] Future: Identify blind spots per user

---

### Phase 1 Success Criteria

**MVP (Challenge Mode Only):**
- ✅ User can click Challenge button and get AI counter-arguments - **ACHIEVED**
- ✅ Response appears smoothly without page reload - **ACHIEVED**
- ✅ Responses are relevant and specific to user's answer - **ACHIEVED**
- ⏳ 60%+ of challenges rated "helpful" by users - **PENDING USER TESTING**
- ⏳ Cost <$0.01 per interaction - **MONITORING IN PROGRESS**
- ✅ No major bugs or errors - **ACHIEVED**

**Full Phase 1 (All Modes):**
- ✅ All 3 new modes working smoothly (Challenge, Elaboration, Fact-Check) - **ACHIEVED**
- ⏳ User can enable/disable modes via settings - **DEFERRED TO PHASE 1.5**
- ⏳ 70%+ helpful rating across all modes - **PENDING USER TESTING**
- ✅ Feedback data being collected for future analysis - **ACHIEVED**
- ⏳ Document analysis preserved (disabled for now, re-enable later) - **PARTIAL**
- ⏳ Average cost <$0.02 per research session - **MONITORING IN PROGRESS**

**Additional Achievements:**
- ✅ Reusable JavaScript module created for platform-wide expansion
- ✅ Complete documentation for future implementations
- ✅ GDPR compliance planning completed
- ✅ Database schema with privacy considerations

---

### ✅ Phase 1 COMPLETE - Implementation Summary

**Completion Date:** 2026-01-18

**What Was Built:**

1. **Backend Infrastructure**
   - AIResearchAssistant service layer (`/app/services/ai_research_assistant.py`)
   - 3 YAML prompt templates (challenge, elaboration, factcheck)
   - Flask routes: `/research/ai_assist`, `/research/ai_assist/feedback`, `/research/ai_assist/regenerate`
   - AIResearchFeedback database model with full tracking
   - Privacy documentation and GDPR compliance TODO

2. **Frontend UI**
   - Unified AI Assistant accordion section in research_step.html
   - 4-card grid layout (Challenge, Elaboration, Fact-Check, Document Analysis)
   - Dynamic feedback buttons (Helpful, Not Helpful, Dismiss)
   - Loading states with mode-specific messages
   - Markdown-style response formatting

3. **JavaScript Module** (**Platform-Wide Reusable**)
   - `/app/static/js/ai-research-assistant.js` - Fully modular class
   - Complete documentation: `/docs/ai_research_assistant_module.md`
   - Ready to import into Decision Journal, Portfolio Notes, Sector Research

4. **Key Fixes During Implementation**
   - Provider/model not passed from YAML → Fixed with enum conversion
   - Default model changed: `gemini-2.5-flash` → `gemini-flash-latest`
   - max_tokens too low (400) → Increased to 5000 for all modes
   - Gemini RECITATION filter triggered → Added prompt clarifications
   - JavaScript selector bug → Fixed element targeting

**Current Status:**
- ✅ All 3 AI modes working in production
- ✅ Feedback tracking operational
- ✅ Reusable module ready for platform expansion
- ⏳ User testing in progress (collect real feedback)
- ⏳ Cost monitoring to validate <$0.01 per interaction target

---

## Phase 1.5: Polish & Refinement (CURRENT PRIORITY)

**Timeline:** During Beta Testing (2-4 weeks)
**Goal:** Optimize AI assistant based on real usage, prepare for scale
**Philosophy:** Iterate based on user feedback, not assumptions

---

### Priority 1: User Feedback Collection & Analysis ⏳

**Objective:** Understand what's working and what needs improvement

**Tasks:**
- Use AI Assistant in real research sessions (dogfood the feature)
- Encourage beta testers to use all 3 modes (Challenge, Elaboration, Fact-Check)
- Monitor AIResearchFeedback table daily (helpful vs not_helpful ratios)
- Identify patterns in feedback (which modes are most helpful?)
- Track which question types benefit most from AI (moat vs risks vs valuation)
- Collect qualitative feedback (user interviews, surveys)
- Identify edge cases where AI fails (generic responses, off-topic, etc.)

**Success Metrics:**
- Achieve 70%+ helpful rating across all modes
- Identify top 3 pain points from user feedback
- Document common failure modes
- Understand which modes users prefer and why

---

### Priority 2: Prompt Engineering & Quality Tuning ⏳

**Objective:** Improve response quality based on real usage patterns

**Tasks:**
- Analyze AI responses that received "not_helpful" feedback
- Identify common issues (too generic, too long, off-topic, not actionable)
- Tune YAML prompt templates based on feedback patterns
- Adjust temperature settings if needed (currently 0.7 for Challenge/Elaboration, 0.5 for Fact-Check)
- Test prompt variations with real user answers
- Consider adding few-shot examples to prompts if quality issues persist
- Balance response length vs cost (currently 5000 max_tokens)
- Ensure responses reference user's specific answer (not generic advice)

**Specific Improvements to Test:**
- Challenge Mode: Ensure counter-arguments are constructive, not dismissive
- Elaboration Mode: Ensure questions are actionable and not too philosophical
- Fact-Check Mode: Ensure claim identification is reasonable (not nitpicky)

**Success Metrics:**
- Reduce "not_helpful" feedback by 50%
- Increase average response quality (subjective but trackable)
- Maintain cost under target ($0.01 per interaction)

---

### Priority 3: Cost Monitoring & Optimization ⏳

**Objective:** Ensure sustainable economics before scaling

**Tasks:**
- Track actual token usage per interaction (from AI provider response)
- Calculate true cost per interaction (accounting for different models)
- Analyze cost distribution (which modes are most expensive?)
- Identify outliers (unusually expensive interactions)
- Test if reducing max_tokens (from 5000) impacts quality
- Consider using different models for different modes (Flash vs Pro)
- Monitor platform-wide daily/weekly AI spend
- Set up alerts if costs exceed thresholds

**Cost Optimization Strategies:**
- If costs too high: Reduce max_tokens, use cheaper models, implement caching
- If costs acceptable: Focus on quality over cost reduction
- Consider A/B testing: Different token limits for different user segments

**Success Metrics:**
- Average cost per interaction < $0.01 (with Gemini Flash)
- Platform daily AI spend predictable and sustainable
- Cost per mode understood and documented

---

### Priority 4: UI/UX Improvements ⏳

**Objective:** Make AI Assistant easier and more delightful to use

**Tasks:**
- Add "Regenerate" button to UI (backend route already exists)
- Improve response formatting (better markdown handling, code blocks if needed)
- Add "Copy to Clipboard" button for AI responses
- Consider "Save to Notes" functionality (persist AI insights)
- Improve loading states (show estimated time remaining?)
- Add tooltips explaining what each mode does (for new users)
- Consider collapsing accordion after response viewed (reduce clutter)
- Test mobile responsiveness (if beta includes mobile users)
- Add keyboard shortcuts for power users (optional)

**Nice-to-Have Features:**
- Conversation history (see previous AI responses for same item)
- Export AI feedback (download as PDF/text)
- Email AI response to self (for later review)

**Success Metrics:**
- User engagement with AI Assistant increases (more interactions per session)
- Positive feedback on UI/UX improvements
- Reduced confusion about how to use feature

---

### Priority 5: User Settings & Personalization ⏳

**Objective:** Let users customize AI Assistant to their preferences

**Tasks:**
- Add settings panel in user preferences/profile page
- Toggle to enable/disable each AI mode (Challenge, Elaboration, Fact-Check)
- Toggle to show/hide AI Assistant accordion entirely (for users who don't want it)
- Save preferences in database (user_preferences table or JSON column)
- Load preferences on page load (respect user choices)
- Add "Reset to Defaults" option
- Consider per-question-type preferences (e.g., only challenge on moat questions)

**Default Settings:**
- All modes enabled for new users
- AI Assistant accordion visible by default
- Can be adjusted based on beta feedback

**Success Metrics:**
- Users engage with settings (shows they care about customization)
- Understand which modes are most commonly disabled (signals quality issues)

---

### Priority 6: Document Analysis Re-Integration (Optional) ⏳

**Objective:** Bring back existing document analysis feature into new UI

**Tasks:**
- Review existing document analysis code (currently disabled)
- Integrate into 4th card in AI Assistant grid
- Ensure document upload/selection UI works
- Test with multiple documents
- Verify LLM prompt extraction still works
- Consider unifying with new AI assistant flow (same feedback mechanism)
- Decide if document analysis counts toward token limits

**Decision Point:**
- If document analysis is rarely used → keep disabled, focus on new modes
- If users request it → re-enable and integrate properly

---

### Priority 7: Error Handling & Edge Cases ⏳

**Objective:** Handle failures gracefully, improve reliability

**Tasks:**
- Test what happens when AI service is down (graceful degradation)
- Handle timeout scenarios (AI takes too long to respond)
- Improve error messages (user-friendly, actionable)
- Test with very long answers (exceeds context window)
- Test with very short answers (< 10 characters - currently blocked)
- Test with non-English answers (if international users)
- Handle malformed responses from AI (parsing errors)
- Add retry logic for transient failures

**Success Metrics:**
- Zero crashes from AI failures
- Users understand what went wrong and how to fix it
- Graceful fallback when AI unavailable

---

### Phase 1.5 Success Criteria

**Must Achieve Before Moving to Phase 2:**
- ✅ 70%+ helpful rating across all modes
- ✅ Cost per interaction validated as sustainable (< $0.01)
- ✅ Feedback collection system working and used by beta testers
- ✅ No critical bugs or usability issues
- ✅ Prompts tuned based on real usage patterns

**Nice to Have (Can Defer):**
- ⏳ Regenerate button implemented in UI
- ⏳ User settings for enabling/disabling modes
- ⏳ Document analysis re-enabled
- ⏳ Advanced formatting features

**When to Move to Phase 2:**
- AI Assistant is polished and users love it
- Economics are sustainable (cost predictable, manageable)
- No major bugs or complaints
- Ready to expand to other features (Decision Journal, Portfolio Notes)

---

### Current Action Items (Week by Week)

**Week 1 (Beta Launch Week):**
- Monitor usage daily (who's using it, how often)
- Collect initial feedback (quick surveys, direct messages)
- Fix any critical bugs immediately
- Track cost and token usage closely

**Week 2-3 (Iteration):**
- Analyze feedback patterns (what's working, what's not)
- Tune prompts based on "not_helpful" responses
- Implement quick UI wins (Regenerate button, etc.)
- Continue monitoring costs

**Week 4 (Validation):**
- Measure success metrics (helpful ratio, cost, engagement)
- Decide if ready for Phase 2 (expand to other features)
- Document lessons learned
- Plan next iteration or expansion

---

**Next Major Phase (After 1.5):**
- **Phase 2:** Expand AI assistant to Decision Journal and Portfolio Notes using reusable module
- **Phase 3:** Analytics dashboard for feedback tracking and quality monitoring
- **Future:** Argos integration - correlate AI challenges with investment outcomes

---

## Phase 2: Research Notes Intelligence (FUTURE)

### Potential Features:

**Pattern Detection:**
- Identify recurring themes across notes for same company
- Flag contradictions in user's notes over time
- Suggest connections between companies (e.g., "Similar moat to [previous research]")

**Synthesis Assistant:**
- "Summarize all notes tagged 'risks'"
- "What changed between initial notes and final decision?"
- Generate timeline of thesis evolution

**Smart Tagging:**
- Auto-suggest tags based on note content
- Link notes to checklist questions
- Cluster notes by topic (financials, moat, risks, etc.)

---

## Phase 3: Decision Journal AI Review (FUTURE)

### Potential Features:

**Thesis Consistency Check:**
- Compare thesis to checklist answers → flag mismatches
- "Your thesis says 'strong moat' but checklist shows 'low switching costs'"

**Bias Detection:**
- Analyze language for overconfidence signals
- Flag FOMO indicators (e.g., "can't miss", "obvious winner")
- Compare to past mistakes with similar language patterns

**Pre-Mortem Generator:**
- "What would need to go wrong for this thesis to fail?"
- Force user to articulate failure modes before investing

---

## Phase 4: Document Analysis Assistant (FUTURE - Tech Not Ready)

### Current State:

**Existing Feature:** "Analyze with AI Assistant" (http://localhost:5000/research/checklist/28/item/93)

**Why Not Now:**
- Requires uploading full documents/context → expensive
- Current AI models not optimized for this (waiting for NotebookLLM-style APIs)
- High cost, uncertain value

**Future Vision:**
- Once APIs like NotebookLLM become available
- Upload earnings transcripts, 10-Ks, research reports
- Ask questions across entire document corpus
- Generate structured insights with citations

**Not a priority until:**
- ✅ Cost-effective document analysis APIs available
- ✅ Phase 1-3 features validated and generating value
- ✅ Clear ROI demonstrated for full-document analysis

---

## Phase 5: Cross-Domain Intelligence (FUTURE - Argos Territory)

### Correlation Analysis:

**Research Quality → Trade Outcomes:**
- Which checklist questions correlated with winners vs losers?
- Do challenged/revised answers perform better?
- Time spent on research vs return quality

**Pattern Recognition:**
- "You always skip exit criteria → disposition effect"
- "Strong moat answers → better long-term returns"
- "FOMO language in notes → bad outcomes"

**Personalized Recommendations:**
- "Based on your history, spend more time on [question type]"
- "Your blind spot: underestimating competitive dynamics"

---

## Success Metrics

**Phase 1 Success:**
- ✅ AI assistant improves answer quality (measured by user revisions)
- ✅ 70%+ of challenges rated "helpful" by users
- ✅ Cost <$0.01 per checklist item
- ✅ Structured data collected for Argos

**Long-term Success (Argos Integration):**
- ✅ Correlation found: Research quality → Trade outcomes
- ✅ Personalized insights: "Your pattern: [X]"
- ✅ Predictive: "This research style → [outcome]"

---

## Notes

- **Start small:** Single feature (devil's advocate) on checklist items only
- **Iterate fast:** Test with real usage, gather feedback
- **Data first:** Every interaction must generate structured data for Argos
- **Cost conscious:** Use Flash models, short prompts, caching
- **User control:** AI suggests/challenges, user decides

---

## Immediate Next Steps

**Current Status:** Phase 1 Implementation Ready - All design decisions finalized

**✅ Decisions Made:**
1. ✅ UI: Option 4 Enhanced (Unified AI Assistant with 4-card grid)
2. ✅ Implementation: Challenge Mode first (MVP), then expand to other modes
3. ✅ Response format: Plain text with formatting
4. ✅ Trigger: On-demand (user clicks card/button)
5. ✅ UX: Smooth JavaScript interactions (no page reloads)
6. ✅ Feedback: Track helpful/not helpful for quality improvement

**🎯 Next Action:**
**Start Step 1.1:** Create YAML prompt templates for Devil's Advocate (Challenge Mode)

**Work in Progress:**
- Creating prompt templates for Challenge, Elaboration, and Fact-Check modes
- Testing prompts with AI service to ensure high-quality responses
- Once prompts validated, move to backend API implementation

**Implementation Philosophy:**
- One step at a time, test thoroughly before moving forward
- Start with MVP (Challenge Mode only), validate, then expand
- Focus on quality over quantity - better to have 1 excellent mode than 3 mediocre ones
- Collect user feedback early and iterate based on real usage

---

## 🎯 Immediate Next Steps (Phase 1.5 - Polish)

**Priority 1: User Testing & Feedback Collection**
1. Use AI Assistant in real research sessions
2. Collect feedback on all 3 modes (Challenge, Elaboration, Fact-Check)
3. Monitor database for feedback trends (helpful vs not_helpful ratio)
4. Identify prompt improvements based on real usage

**Priority 2: Cost Monitoring**
1. Track token usage per interaction
2. Calculate actual cost per research session
3. Verify <$0.01 per interaction target
4. Adjust max_tokens if needed to optimize cost

**Priority 3: UI Enhancements**
1. Add "Regenerate" button to UI (backend already exists)
2. Improve response formatting (better markdown handling)
3. Consider adding "Save to Notes" functionality
4. Polish loading states and error messages

**Priority 4: Platform Expansion**
1. Add AI Assistant to Decision Journal (reuse module)
2. Add AI Assistant to Portfolio Notes (reuse module)
3. Test module reusability across different contexts

**Priority 5: Settings & Preferences (Step 5)**
1. Add user settings panel to enable/disable modes
2. Store preferences in database
3. Default all modes enabled, allow customization
4. Consider admin toggle for feature flags

**When to Move to Phase 2:**
- ✅ 70%+ helpful rating achieved across all modes
- ✅ Cost validated as sustainable
- ✅ No major bugs or usability issues
- ✅ AI Assistant expanded to at least 1 other feature (Decision Journal or Portfolio)

---

## 📊 Success Tracking

**KPIs to Monitor:**
- Feedback helpful ratio (target: 70%+)
- Cost per interaction (target: <$0.01)
- Usage frequency (which modes used most)
- Answer revision rate (do users edit after AI challenge?)
- Time to complete research (does AI speed up or slow down?)

**Future Argos Correlation:**
- Research items with AI challenges → investment outcomes
- Users who revise answers after AI feedback → better returns?
- Question types that benefit most from AI assistance → prioritize those
