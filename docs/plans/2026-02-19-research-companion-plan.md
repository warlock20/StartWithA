# Research Companion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered Research Companion that enriches Argos with mistake/journal/pattern history, provides pre-session research briefs, a facts-only live companion chat, counter-evidence generation, quick-capture from external sources, and session wrap-ups.

**Architecture:** Extend the existing `ArgosService` (`app/services/argos/core.py`) to be the single orchestrator for all companion features. Add new insight categories (journal, patterns) for data gathering, and new companion methods (`build_research_context()`, `generate_brief()`, `ask_companion()`, `generate_counter_evidence()`, `wrap_up_session()`) for feature delivery. No separate companion service — Argos is the orchestrator. Add a `ResearchCapture` model for the bookmarklet quick-capture flow. All AI interactions go through existing YAML prompt templates.

**Tech Stack:** Flask, SQLAlchemy, Celery + Redis, AIService (Gemini/Claude), PromptService (YAML templates), pgvector embeddings

**Design Doc:** `docs/plans/2026-02-19-research-companion-design.md`

---

## Task 1: Argos Enrichment — Add Journal & Pattern Insight Categories

Extend Argos to surface DecisionJournal entries and PatternRecognition records alongside existing mistake log matches.

**Files:**
- Modify: `app/services/argos/config.py:19-26` (add new InsightCategory values)
- Modify: `app/services/argos/config.py:56-85` (add new categories to CONTEXT_RULE_MATRIX)
- Modify: `app/services/argos/core.py:157-163` (add new gather methods to method_map)
- Modify: `app/services/argos/core.py` (add `_gather_journal_insights` and `_gather_pattern_warnings` methods)
- Test: `unittests/test_argos_enrichment.py`

**Step 1: Write failing tests for journal and pattern gathering**

```python
#!/usr/bin/env python3
"""Test Argos enrichment with journal entries and pattern recognition data"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.config import InsightCategory, CONTEXT_RULE_MATRIX


def test_insight_categories_include_journal_and_pattern():
    """InsightCategory enum has JOURNAL_INSIGHT and PATTERN_WARNING"""
    assert hasattr(InsightCategory, 'JOURNAL_INSIGHT'), "Missing JOURNAL_INSIGHT category"
    assert hasattr(InsightCategory, 'PATTERN_WARNING'), "Missing PATTERN_WARNING category"
    assert InsightCategory.JOURNAL_INSIGHT.value == 'journal_insight'
    assert InsightCategory.PATTERN_WARNING.value == 'pattern_warning'
    print("PASS: InsightCategory has journal and pattern categories")


def test_context_rule_matrix_includes_new_categories():
    """CONTEXT_RULE_MATRIX includes JOURNAL_INSIGHT and PATTERN_WARNING for all step types"""
    for step_type in ['checklist', 'free_research', 'thesis', 'completion']:
        rules = CONTEXT_RULE_MATRIX[step_type]
        assert InsightCategory.JOURNAL_INSIGHT in rules, f"Missing JOURNAL_INSIGHT in {step_type}"
        assert InsightCategory.PATTERN_WARNING in rules, f"Missing PATTERN_WARNING in {step_type}"
    print("PASS: CONTEXT_RULE_MATRIX includes new categories")


if __name__ == '__main__':
    test_insight_categories_include_journal_and_pattern()
    test_context_rule_matrix_includes_new_categories()
    print("\nAll Argos enrichment tests passed!")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_argos_enrichment.py`
Expected: FAIL with `AssertionError: Missing JOURNAL_INSIGHT category`

**Step 3: Add new InsightCategory values**

In `app/services/argos/config.py`, add to the `InsightCategory` enum (after line 25):

```python
class InsightCategory(Enum):
    """Categories of Argos insights"""
    MISTAKE_MATCH = 'mistake_match'
    LOSS_PATTERN = 'loss_pattern'
    ACCOUNTING_FLAG = 'accounting_flag'
    CONSISTENCY = 'consistency'
    COMPLETENESS = 'completeness'
    JOURNAL_INSIGHT = 'journal_insight'
    PATTERN_WARNING = 'pattern_warning'
```

Add to `CONTEXT_RULE_MATRIX` — journal and pattern insights should be active for all step types:

```python
CONTEXT_RULE_MATRIX: Dict[str, Dict[str, bool | str]] = {
    'checklist': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: 'financial',
        InsightCategory.CONSISTENCY: True,
        InsightCategory.COMPLETENESS: False,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'free_research': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: 'keywords',
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: False,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'thesis': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: True,
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: False,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'completion': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: True,
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: True,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
}
```

Add confidence rules for new categories:

```python
CONFIDENCE_RULES = {
    # ... existing rules ...
    InsightCategory.JOURNAL_INSIGHT: {
        'base': ConfidenceLevel.MEDIUM,
    },
    InsightCategory.PATTERN_WARNING: {
        'base': ConfidenceLevel.HIGH,  # User-identified patterns are high value
    },
}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_argos_enrichment.py`
Expected: PASS

**Step 5: Implement `_gather_journal_insights` in `app/services/argos/core.py`**

Add to the `method_map` dict in `_gather_candidates` (line ~157):

```python
method_map = {
    InsightCategory.MISTAKE_MATCH: self._gather_mistake_matches,
    InsightCategory.LOSS_PATTERN: self._gather_loss_patterns,
    InsightCategory.ACCOUNTING_FLAG: self._gather_accounting_flags,
    InsightCategory.CONSISTENCY: self._gather_consistency_issues,
    InsightCategory.COMPLETENESS: self._gather_completeness_issues,
    InsightCategory.JOURNAL_INSIGHT: self._gather_journal_insights,
    InsightCategory.PATTERN_WARNING: self._gather_pattern_warnings,
}
```

Add the new methods:

```python
def _gather_journal_insights(
    self,
    company,
    step_context: Dict[str, Any],
    current_text: Optional[str],
) -> tuple[List[InsightCandidate], List[str], List[str]]:
    """
    Find relevant DecisionJournal entries for this company/sector.

    Surfaces: past decisions, outcomes, lessons learned for the same
    company or sector — so the user sees their own history.
    """
    from app.models.journal import DecisionJournal

    candidates = []
    checks_passed = []
    checks_failed = []

    # Get journal entries for same company
    company_journals = DecisionJournal.query.filter_by(
        user_id=self.user_id,
        company_id=company.id,
    ).all()

    for journal in company_journals:
        candidates.append(InsightCandidate(
            category=InsightCategory.JOURNAL_INSIGHT,
            source_type='decision_journal',
            source_id=journal.id,
            raw_data={
                'id': journal.id,
                'decision_type': journal.decision_type,
                'decision_date': str(journal.decision_date) if journal.decision_date else None,
                'confidence_score': journal.confidence_score,
                'investment_thesis': (journal.investment_thesis or '')[:300],
                'lessons_learned': (journal.lessons_learned or '')[:300],
                'what_went_wrong': (journal.what_went_wrong or '')[:300],
                'actual_return': journal.actual_return,
                'would_repeat': journal.would_repeat,
                'company_name': company.name,
            },
            match_reason='same_company',
            base_confidence=ConfidenceLevel.HIGH,
        ))

    # Get journal entries for same sector
    company_sector = self._get_company_sector(company.id)
    if company_sector:
        from app.models.company import Company
        sector_company_ids = [
            c.id for c in Company.query.filter_by(user_id=self.user_id).all()
            if self._get_company_sector(c.id) and
               self._get_company_sector(c.id).lower() == company_sector.lower() and
               c.id != company.id
        ]
        if sector_company_ids:
            sector_journals = DecisionJournal.query.filter(
                DecisionJournal.user_id == self.user_id,
                DecisionJournal.company_id.in_(sector_company_ids),
            ).all()

            for journal in sector_journals:
                candidates.append(InsightCandidate(
                    category=InsightCategory.JOURNAL_INSIGHT,
                    source_type='decision_journal',
                    source_id=journal.id,
                    raw_data={
                        'id': journal.id,
                        'decision_type': journal.decision_type,
                        'decision_date': str(journal.decision_date) if journal.decision_date else None,
                        'confidence_score': journal.confidence_score,
                        'investment_thesis': (journal.investment_thesis or '')[:300],
                        'lessons_learned': (journal.lessons_learned or '')[:300],
                        'actual_return': journal.actual_return,
                        'company_name': getattr(journal, 'company', None) and journal.company.name or 'Unknown',
                    },
                    match_reason='sector_match',
                    base_confidence=ConfidenceLevel.MEDIUM,
                    matched_sector=True,
                ))

    logger.debug(f"JournalInsight found {len(candidates)} candidates")
    return candidates, checks_passed, checks_failed


def _gather_pattern_warnings(
    self,
    company,
    step_context: Dict[str, Any],
    current_text: Optional[str],
) -> tuple[List[InsightCandidate], List[str], List[str]]:
    """
    Surface PatternRecognition entries (failure patterns, behavioral patterns).

    These are user-identified or AI-detected patterns that should be front
    of mind during research.
    """
    from app.models.journal import PatternRecognition

    candidates = []
    checks_passed = []
    checks_failed = []

    # Get failure and behavioral patterns (most relevant during research)
    patterns = PatternRecognition.query.filter(
        PatternRecognition.user_id == self.user_id,
        PatternRecognition.pattern_type.in_(['failure_pattern', 'behavioral']),
    ).all()

    for pattern in patterns:
        candidates.append(InsightCandidate(
            category=InsightCategory.PATTERN_WARNING,
            source_type='pattern_recognition',
            source_id=pattern.id,
            raw_data={
                'id': pattern.id,
                'pattern_name': pattern.pattern_name,
                'pattern_type': pattern.pattern_type,
                'description': (pattern.description or '')[:300],
                'occurrences': pattern.occurrences,
                'impact_score': pattern.impact_score,
                'how_to_avoid': (pattern.how_to_avoid or '')[:300],
                'confidence_level': pattern.confidence_level,
                'last_observed': str(pattern.last_observed) if pattern.last_observed else None,
            },
            match_reason='active_pattern',
            base_confidence=ConfidenceLevel.HIGH if (pattern.impact_score or 0) >= 7 else ConfidenceLevel.MEDIUM,
            matched_tags=[pattern.pattern_type] if pattern.pattern_type else [],
        ))

    logger.debug(f"PatternWarning found {len(candidates)} candidates")
    return candidates, checks_passed, checks_failed
```

Also update `_build_summary` and `_build_source_label` to handle new source types:

```python
def _build_summary(self, candidate: InsightCandidate) -> str:
    raw = candidate.raw_data
    if candidate.source_type == 'mistake_log':
        return raw.get('title', 'Mistake log entry')
    elif candidate.source_type == 'trade_loss':
        return f"Loss on {raw.get('company_name', 'Unknown')}: {raw.get('return_pct', 0):.1f}%"
    elif candidate.source_type == 'decision_journal':
        decision_type = raw.get('decision_type', 'unknown')
        company = raw.get('company_name', 'Unknown')
        return f"Past {decision_type} decision on {company}"
    elif candidate.source_type == 'pattern_recognition':
        return raw.get('pattern_name', 'Behavioral pattern')
    return raw.get('summary', 'Insight')


def _build_source_label(self, candidate: InsightCandidate) -> str:
    if candidate.source_type == 'mistake_log':
        return f"Mistake #{candidate.source_id}"
    elif candidate.source_type == 'trade_loss':
        return f"Trade: {candidate.raw_data.get('company_name', 'Unknown')}"
    elif candidate.source_type == 'decision_journal':
        return f"Decision Journal #{candidate.source_id}"
    elif candidate.source_type == 'pattern_recognition':
        return f"Pattern: {candidate.raw_data.get('pattern_name', 'Unknown')}"
    return f"{candidate.source_type} #{candidate.source_id}"
```

**Step 6: Run test to verify it passes**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_argos_enrichment.py`
Expected: PASS

**Step 7: Commit**

```bash
git add app/services/argos/config.py app/services/argos/core.py unittests/test_argos_enrichment.py
git commit -m "feat: enrich Argos with journal insights and pattern warnings"
```

---

## Task 2: Companion Prompt Templates

Create YAML prompt templates for research brief, live companion, counter-evidence, and session wrap-up.

**Files:**
- Create: `app/services/ai/prompts/companion/research_brief.yaml`
- Create: `app/services/ai/prompts/companion/live_companion.yaml`
- Create: `app/services/ai/prompts/companion/counter_evidence.yaml`
- Create: `app/services/ai/prompts/companion/session_wrapup.yaml`
- Test: `unittests/test_companion_prompts.py`

**Step 1: Write failing test for prompt loading**

```python
#!/usr/bin/env python3
"""Test companion prompt templates load correctly"""

import yaml
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PROMPTS_DIR = Path(__file__).parent.parent / "app" / "services" / "ai" / "prompts" / "companion"

REQUIRED_PROMPTS = [
    'research_brief',
    'live_companion',
    'counter_evidence',
    'session_wrapup',
]

REQUIRED_FIELDS = ['name', 'description', 'version', 'category', 'system_context', 'template']


def test_all_companion_prompts_exist():
    """All companion prompt YAML files exist"""
    assert PROMPTS_DIR.exists(), f"Companion prompts directory missing: {PROMPTS_DIR}"
    for name in REQUIRED_PROMPTS:
        path = PROMPTS_DIR / f"{name}.yaml"
        assert path.exists(), f"Missing prompt: {path}"
    print("PASS: All companion prompt files exist")


def test_all_companion_prompts_valid():
    """All companion prompts have required fields and valid templates"""
    for name in REQUIRED_PROMPTS:
        path = PROMPTS_DIR / f"{name}.yaml"
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        for field in REQUIRED_FIELDS:
            assert field in data, f"{name}.yaml missing required field: {field}"

        assert data['category'] == 'companion', f"{name}.yaml category should be 'companion'"
    print("PASS: All companion prompts have valid structure")


def test_live_companion_has_opinion_warning():
    """Live companion prompt includes opinion-warning rules"""
    path = PROMPTS_DIR / "live_companion.yaml"
    with open(path, 'r') as f:
        content = f.read()
    assert 'opinion' in content.lower(), "live_companion.yaml must include opinion-warning rules"
    print("PASS: Live companion includes opinion-warning rules")


if __name__ == '__main__':
    test_all_companion_prompts_exist()
    test_all_companion_prompts_valid()
    test_live_companion_has_opinion_warning()
    print("\nAll companion prompt tests passed!")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_companion_prompts.py`
Expected: FAIL with `AssertionError: Companion prompts directory missing`

**Step 3: Create the prompt templates**

Create `app/services/ai/prompts/companion/research_brief.yaml`:

```yaml
name: "research_brief"
description: "Generate a pre-session research brief for a research step"
version: "1.0"
category: "companion"

preferred_provider: "gemini"
model: "gemini-2.5-flash"
max_tokens: 800
temperature: 0.3

system_context: |
  You are a research assistant helping an investor prepare for a focused research session.
  Your role is to summarize what's known, what's unknown, and what to look for next.
  Be specific and actionable. Never give investment opinions or recommendations.
  Surface facts, gaps, and historical context only.

template: |
  COMPANY: {company_name}
  SECTOR: {sector_name}
  CURRENT STEP: {step_name}
  STEP DESCRIPTION: {step_description}

  RESEARCH QUESTIONS FOR THIS STEP:
  {research_questions}

  FINDINGS SO FAR (from prior steps):
  {prior_findings}

  KEY FLAGS:
  Red flags: {red_flags}
  Green flags: {green_flags}

  CURRENT THESIS:
  {investment_thesis}

  HISTORY WITH THIS COMPANY/SECTOR:
  Past decisions: {journal_summary}
  Past mistakes: {mistake_summary}
  Behavioral patterns to watch: {pattern_summary}

  Generate a research brief with:
  1. WHAT YOU'RE ANSWERING: List the specific research questions for this step
  2. WHAT YOU ALREADY KNOW: Summarize key findings from prior steps (2-3 sentences)
  3. THREE THINGS TO LOOK FOR: Three specific, concrete things to investigate in the next 30 minutes
  4. WATCH OUT: Any warnings from your history (past mistakes in this sector, behavioral patterns)

  Keep it concise. No opinions. Facts and gaps only.

output_format: |
  Structured text with clear section headers.
  Each section should be 1-3 sentences maximum.
  "Three things to look for" should be numbered with specific search suggestions.
```

Create `app/services/ai/prompts/companion/live_companion.yaml`:

```yaml
name: "live_companion"
description: "Answer research questions during a session, surfacing facts not opinions"
version: "1.0"
category: "companion"

preferred_provider: "gemini"
model: "gemini-2.5-flash"
max_tokens: 600
temperature: 0.3

system_context: |
  You are a research companion helping an investor during an active research session.

  CRITICAL RULES:
  1. You surface FACTS, DATA, and INFORMATION. You NEVER give investment opinions.
  2. If the user asks "Should I invest?", "Is this a good company?", "What do you think?"
     or any opinion-seeking question, respond with:
     "Forming the investment opinion is your job — that's where your edge comes from.
     I can show you what the data says and what you might be missing."
     Then follow up with relevant facts from their research context.
  3. When suggesting what to research, frame it as "Your research questions suggest looking at..."
     not "You should look at..."
  4. When highlighting gaps, say "Question X has no findings yet" not "You need to research X"
  5. Reference the user's own history (mistakes, patterns) as facts: "Your mistake log shows..."
     not "You tend to..."

template: |
  RESEARCH CONTEXT:
  Company: {company_name} | Sector: {sector_name}
  Current Step: {step_name}

  Research Questions:
  {research_questions}

  Findings So Far:
  {current_findings}

  Thesis: {investment_thesis}

  User's History:
  {history_context}

  CONVERSATION SO FAR:
  {conversation_history}

  USER'S QUESTION: {user_question}

  Respond following the critical rules above. Be concise (2-4 sentences).
  Surface relevant facts from the research context. Highlight gaps if relevant.

output_format: |
  Plain text, 2-4 sentences. No headers or bullet points unless listing specific data points.
```

Create `app/services/ai/prompts/companion/counter_evidence.yaml`:

```yaml
name: "counter_evidence"
description: "Generate counter-evidence for a research finding"
version: "1.0"
category: "companion"

preferred_provider: "gemini"
model: "gemini-2.5-flash"
max_tokens: 600
temperature: 0.4

system_context: |
  You are a devil's advocate for investment research. When given a finding, your job is to
  surface facts, data points, and considerations that could CONTRADICT or WEAKEN that finding.

  You do NOT say the finding is wrong. You say "Here are facts that could challenge this finding."
  Present counter-evidence as information to consider, not as conclusions.
  Be specific — name concrete risks, competitors, trends, or data points.

template: |
  COMPANY: {company_name}
  SECTOR: {sector_name}

  THE FINDING:
  {finding_text}

  CONTEXT (what the user is researching):
  Research question: {research_question}
  Current thesis: {investment_thesis}

  Generate 2-3 specific counter-evidence points that could challenge this finding.
  For each point:
  1. State the counter-evidence as a fact or data point
  2. Suggest a specific source or search query to verify it

  Do NOT say the finding is wrong. Present information that the researcher should consider.

output_format: |
  Numbered list, 2-3 items. Each item has:
  - The counter-evidence point (1-2 sentences)
  - A verification suggestion: "To verify: [specific search query or source]"
```

Create `app/services/ai/prompts/companion/session_wrapup.yaml`:

```yaml
name: "session_wrapup"
description: "Summarize a research session: accomplishments, gaps, next steps"
version: "1.0"
category: "companion"

preferred_provider: "gemini"
model: "gemini-2.5-flash"
max_tokens: 600
temperature: 0.3

system_context: |
  You are summarizing a research session for an investor. Be factual and concise.
  Focus on what was accomplished, what's still open, and what to focus on next.
  Never give investment opinions. Report facts about the research progress.

template: |
  COMPANY: {company_name}
  STEP: {step_name}
  SESSION DURATION: {duration_minutes} minutes

  RESEARCH QUESTIONS FOR THIS STEP:
  {research_questions}

  FINDINGS ADDED THIS SESSION:
  {session_findings}

  ALL FINDINGS (cumulative):
  {all_findings}

  COUNTER-EVIDENCE GENERATED:
  {counter_evidence}

  Summarize this research session:
  1. ACCOMPLISHED: What questions were addressed this session (1-2 sentences)
  2. STRONGEST FINDING: The most significant finding from this session
  3. BIGGEST GAP: The most important unanswered question
  4. COUNTER-EVIDENCE TO VERIFY: Any counter-evidence that needs follow-up
  5. NEXT SESSION: What to focus on in the next research session (be specific)

output_format: |
  Structured text with numbered sections matching the template above.
  Each section should be 1-2 sentences maximum.
```

**Step 4: Run test to verify it passes**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_companion_prompts.py`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/ai/prompts/companion/ unittests/test_companion_prompts.py
git commit -m "feat: add companion prompt templates (brief, chat, counter-evidence, wrapup)"
```

---

## Task 3: ResearchCapture Model

Add the `ResearchCapture` model for the quick-capture bookmarklet flow. Add `session_history` JSON field to `ResearchProject`.

**Files:**
- Create: `app/models/research_capture.py`
- Modify: `app/models/research.py:135-294` (add `session_history` field to ResearchProject)
- Modify: `app/models/__init__.py` (register new model)
- Create: migration file
- Test: `unittests/test_research_capture_model.py`

**Step 1: Write failing test**

```python
#!/usr/bin/env python3
"""Test ResearchCapture model exists and has correct fields"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_research_capture_model_importable():
    """ResearchCapture model can be imported"""
    from app.models.research_capture import ResearchCapture
    assert ResearchCapture is not None
    print("PASS: ResearchCapture model importable")


def test_research_capture_has_required_fields():
    """ResearchCapture has all required columns"""
    from app.models.research_capture import ResearchCapture
    required = ['id', 'user_id', 'text', 'url', 'source_title',
                'project_id', 'step_index', 'status', 'captured_at']
    for field in required:
        assert hasattr(ResearchCapture, field), f"Missing field: {field}"
    print("PASS: ResearchCapture has all required fields")


def test_research_project_has_session_history():
    """ResearchProject has session_history JSON field"""
    from app.models.research import ResearchProject
    assert hasattr(ResearchProject, 'session_history'), "Missing session_history field"
    print("PASS: ResearchProject has session_history")


if __name__ == '__main__':
    test_research_capture_model_importable()
    test_research_capture_has_required_fields()
    test_research_project_has_session_history()
    print("\nAll model tests passed!")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_research_capture_model.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.research_capture'`

**Step 3: Create ResearchCapture model**

Create `app/models/research_capture.py`:

```python
"""
ResearchCapture Model

Stores quick-capture findings from external sources (bookmarklet, paste)
before they are assigned to a specific research project step.
"""

from app import db
from app.utils.time_utils import now_utc


class ResearchCapture(db.Model):
    __tablename__ = 'research_capture'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(2048), nullable=True)
    source_title = db.Column(db.String(500), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=True, index=True)
    step_index = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='unassigned', index=True)
    captured_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    # Relationships
    user = db.relationship('User', backref=db.backref('research_captures', lazy='dynamic'))
    project = db.relationship('ResearchProject', backref=db.backref('captures', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'url': self.url,
            'source_title': self.source_title,
            'project_id': self.project_id,
            'step_index': self.step_index,
            'status': self.status,
            'captured_at': self.captured_at.isoformat() if self.captured_at else None,
        }
```

**Step 4: Add `session_history` to ResearchProject**

In `app/models/research.py`, add after the existing `key_findings` field (around line 250):

```python
    session_history = db.Column(db.JSON, nullable=True)  # Array of session wrap-up summaries
```

**Step 5: Register in `app/models/__init__.py`**

Add the import for ResearchCapture alongside existing model imports.

**Step 6: Create migration**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python -m flask db migrate -m "Add ResearchCapture model and session_history to ResearchProject"`

Then run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python -m flask db upgrade`

**Step 7: Run test to verify it passes**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_research_capture_model.py`
Expected: PASS

**Step 8: Commit**

```bash
git add app/models/research_capture.py app/models/research.py app/models/__init__.py migrations/
git commit -m "feat: add ResearchCapture model and session_history field"
```

---

## Task 4: Companion Methods on ArgosService

Add companion methods directly to `ArgosService`: context building, research brief, live chat, counter-evidence, and session wrap-up. Argos is the single orchestrator — no separate service.

**Files:**
- Modify: `app/services/argos/core.py` (add companion methods + CompanionContext dataclass)
- Modify: `app/services/argos/__init__.py` (export new symbols)
- Test: `unittests/test_argos_companion.py`

**Step 1: Write failing test**

```python
#!/usr/bin/env python3
"""Test ArgosService has companion methods"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_argos_has_companion_context():
    """CompanionContext dataclass exists in argos module"""
    from app.services.argos.core import CompanionContext
    assert CompanionContext is not None
    print("PASS: CompanionContext importable from argos")


def test_argos_has_companion_methods():
    """ArgosService has all companion methods"""
    from app.services.argos.core import ArgosService
    required_methods = [
        'build_research_context',
        'generate_brief',
        'ask_companion',
        'generate_counter_evidence',
        'wrap_up_session',
    ]
    for method in required_methods:
        assert hasattr(ArgosService, method), f"Missing method: {method}"
    print("PASS: ArgosService has all companion methods")


def test_companion_context_serializes():
    """CompanionContext.to_dict() works correctly"""
    from app.services.argos.core import CompanionContext
    context = CompanionContext(
        company_name='Test Corp',
        company_id=1,
        sector_name='Technology',
        step_name='Competitive Analysis',
        step_description='Analyze competitive position',
        step_index=2,
        research_questions='- What is the competitive moat?',
        prior_findings='- Strong market position',
        red_flags='High debt ratio',
        green_flags='Strong cash flow',
        investment_thesis='Durable moat due to switching costs',
        journal_summary='No prior decisions',
        mistake_summary='No past mistakes',
        pattern_summary='- Confirmation bias (impact: 8/10)',
    )
    d = context.to_dict()
    assert d['company_name'] == 'Test Corp'
    assert d['pattern_summary'] == '- Confirmation bias (impact: 8/10)'
    assert 'journal_summary' in d
    assert 'mistake_summary' in d
    print("PASS: CompanionContext serializes correctly")


if __name__ == '__main__':
    test_argos_has_companion_context()
    test_argos_has_companion_methods()
    test_companion_context_serializes()
    print("\nAll Argos companion tests passed!")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_argos_companion.py`
Expected: FAIL with `ImportError: cannot import name 'CompanionContext'`

**Step 3: Add CompanionContext dataclass to `app/services/argos/core.py`**

Add at the top of `core.py`, after the existing imports:

```python
from dataclasses import dataclass, asdict


@dataclass
class CompanionContext:
    """Assembled context for companion features. Used by all companion methods."""
    company_name: str
    company_id: int
    sector_name: str
    step_name: str
    step_description: str
    step_index: int
    research_questions: str
    prior_findings: str
    red_flags: str
    green_flags: str
    investment_thesis: str
    journal_summary: str
    mistake_summary: str
    pattern_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
```

**Step 4: Add companion methods to `ArgosService`**

Add these methods to the `ArgosService` class, after the existing helper methods section:

```python
    # =========================================================================
    # Companion Features
    # =========================================================================

    @property
    def _ai_service(self):
        """Lazy load AIService."""
        if not hasattr(self, '__ai_service'):
            from app.services.ai import get_ai_service
            self.__ai_service = get_ai_service()
        return self.__ai_service

    @property
    def _prompt_service(self):
        """Lazy load PromptService."""
        if not hasattr(self, '__prompt_service'):
            from app.services.ai.prompt_service import prompt_service
            self.__prompt_service = prompt_service
        return self.__prompt_service

    def build_research_context(self, project_id: int, step_index: Optional[int] = None) -> CompanionContext:
        """
        Build enriched context from ResearchProject + history data.

        Assembles: company, step, questions, findings, flags, thesis,
        plus mistake log, journal entries, and patterns.
        """
        from app.models.research import ResearchProject

        project = ResearchProject.query.get(project_id)
        if not project or project.user_id != self.user_id:
            raise ValueError(f"Project {project_id} not found or access denied")

        company = project.company
        if step_index is None:
            step_index = project.current_step_index or 0

        # Get step info from template
        step = project.template.get_step(step_index) if project.template else None
        step_name = step.get('name', f'Step {step_index + 1}') if step else f'Step {step_index + 1}'
        step_description = step.get('description', '') if step else ''

        # Get research questions for this step
        research_questions = self._extract_research_questions(project, step, step_index)

        # Get prior findings
        prior_findings = self._format_prior_findings(project, step_index)

        # Get flags
        red_flags = ', '.join(project.red_flags or []) or 'None identified yet'
        green_flags = ', '.join(project.green_flags or []) or 'None identified yet'

        # Thesis
        investment_thesis = project.investment_thesis or 'Not yet formed'

        # Sector
        sector_name = 'Unknown'
        if company and hasattr(company, 'sector') and company.sector:
            sector_name = company.sector.name if hasattr(company.sector, 'name') else str(company.sector)

        # --- Enrichment: mistakes, journals, patterns ---
        journal_summary = self._build_journal_summary(company.id, sector_name)
        mistake_summary = self._build_mistake_summary(company.id, sector_name)
        pattern_summary = self._build_pattern_summary()

        return CompanionContext(
            company_name=company.name if company else 'Unknown',
            company_id=company.id if company else 0,
            sector_name=sector_name,
            step_name=step_name,
            step_description=step_description,
            step_index=step_index,
            research_questions=research_questions,
            prior_findings=prior_findings,
            red_flags=red_flags,
            green_flags=green_flags,
            investment_thesis=investment_thesis,
            journal_summary=journal_summary,
            mistake_summary=mistake_summary,
            pattern_summary=pattern_summary,
        )

    def generate_brief(self, context: CompanionContext) -> str:
        """Generate a pre-session research brief."""
        try:
            prompt = self._prompt_service.get_prompt(
                'companion', 'research_brief', **context.to_dict()
            )
            return self._ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Failed to generate research brief: {e}")
            return f"Could not generate brief: {e}"

    def ask_companion(
        self,
        context: CompanionContext,
        user_question: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Answer a user question during research. Facts only, no opinions."""
        try:
            history_text = '\n'.join(
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in conversation_history[-10:]
            ) or 'No prior conversation'

            prompt = self._prompt_service.get_prompt(
                'companion', 'live_companion',
                company_name=context.company_name,
                sector_name=context.sector_name,
                step_name=context.step_name,
                research_questions=context.research_questions,
                current_findings=context.prior_findings,
                investment_thesis=context.investment_thesis,
                history_context=f"Mistakes: {context.mistake_summary}\nPatterns: {context.pattern_summary}\nPast decisions: {context.journal_summary}",
                conversation_history=history_text,
                user_question=user_question,
            )
            return self._ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Companion chat failed: {e}")
            return f"Could not process question: {e}"

    def generate_counter_evidence(
        self,
        context: CompanionContext,
        finding_text: str,
        research_question: str = '',
    ) -> str:
        """Generate counter-evidence for a research finding."""
        try:
            prompt = self._prompt_service.get_prompt(
                'companion', 'counter_evidence',
                company_name=context.company_name,
                sector_name=context.sector_name,
                finding_text=finding_text,
                research_question=research_question or context.research_questions,
                investment_thesis=context.investment_thesis,
            )
            return self._ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Counter-evidence generation failed: {e}")
            return f"Could not generate counter-evidence: {e}"

    def wrap_up_session(
        self,
        context: CompanionContext,
        session_findings: List[str],
        duration_minutes: int,
        counter_evidence: List[str] = None,
    ) -> str:
        """Generate a session wrap-up summary."""
        try:
            prompt = self._prompt_service.get_prompt(
                'companion', 'session_wrapup',
                company_name=context.company_name,
                step_name=context.step_name,
                duration_minutes=str(duration_minutes),
                research_questions=context.research_questions,
                session_findings='\n'.join(session_findings) or 'No findings added this session',
                all_findings=context.prior_findings,
                counter_evidence='\n'.join(counter_evidence or []) or 'None generated',
            )
            return self._ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Session wrap-up failed: {e}")
            return f"Could not generate wrap-up: {e}"

    # =========================================================================
    # Companion Context Helpers
    # =========================================================================

    def _extract_research_questions(self, project, step, step_index: int) -> str:
        """Extract research questions for the current step."""
        questions = []
        if step and step.get('config', {}).get('questions'):
            questions.extend(step['config']['questions'])
        if step and step.get('type') == 'free_research':
            from app.models.research import FreeResearchQuestion
            free_questions = FreeResearchQuestion.query.filter_by(
                project_id=project.id, step_index=step_index,
            ).all()
            questions.extend([q.question_text for q in free_questions])
        return '\n'.join(f"- {q}" for q in questions) if questions else 'No specific questions defined for this step'

    def _format_prior_findings(self, project, current_step_index: int) -> str:
        """Format findings from prior steps."""
        findings = []
        if project.key_findings:
            findings.extend(project.key_findings)
        if project.step_results:
            for idx_str, result in project.step_results.items():
                if int(idx_str) < current_step_index:
                    if isinstance(result, str):
                        findings.append(result[:200])
                    elif isinstance(result, dict):
                        findings.append(str(result.get('summary', ''))[:200])
        if project.step_notes:
            for idx_str, notes in project.step_notes.items():
                if int(idx_str) < current_step_index and notes and notes != '[SKIPPED]':
                    if isinstance(notes, str):
                        findings.append(notes[:200])
        return '\n'.join(f"- {f}" for f in findings[:20]) if findings else 'No findings yet'

    def _build_journal_summary(self, company_id: int, sector_name: str) -> str:
        """Summarize relevant journal entries."""
        from app.models.journal import DecisionJournal
        entries = DecisionJournal.query.filter_by(
            user_id=self.user_id, company_id=company_id,
        ).all()
        if not entries:
            return 'No prior decisions for this company'
        parts = []
        for e in entries[:5]:
            outcome = f', outcome: {e.actual_return:.1f}%' if e.actual_return is not None else ''
            parts.append(f"- {e.decision_type} (confidence: {e.confidence_score}/10{outcome})")
        return '\n'.join(parts)

    def _build_mistake_summary(self, company_id: int, sector_name: str) -> str:
        """Summarize relevant mistakes."""
        from app.models.idea_pipeline import MistakeLog
        mistakes = list(MistakeLog.query.filter_by(
            user_id=self.user_id, company_id=company_id,
        ).all())
        if sector_name and sector_name != 'Unknown':
            from app.models.company import Company
            sector_companies = Company.query.filter_by(user_id=self.user_id).all()
            sector_company_ids = [
                c.id for c in sector_companies
                if hasattr(c, 'sector') and c.sector
                and (c.sector.name if hasattr(c.sector, 'name') else str(c.sector)).lower() == sector_name.lower()
                and c.id != company_id
            ]
            if sector_company_ids:
                sector_mistakes = MistakeLog.query.filter(
                    MistakeLog.user_id == self.user_id,
                    MistakeLog.company_id.in_(sector_company_ids),
                ).all()
                mistakes.extend(sector_mistakes)
        if not mistakes:
            return 'No past mistakes for this company/sector'
        parts = []
        for m in mistakes[:5]:
            parts.append(f"- {m.title}: {(m.lesson_learned or 'No lesson recorded')[:100]}")
        return '\n'.join(parts)

    def _build_pattern_summary(self) -> str:
        """Summarize active behavioral and failure patterns."""
        from app.models.journal import PatternRecognition
        patterns = PatternRecognition.query.filter(
            PatternRecognition.user_id == self.user_id,
            PatternRecognition.pattern_type.in_(['failure_pattern', 'behavioral']),
        ).order_by(PatternRecognition.impact_score.desc()).limit(5).all()
        if not patterns:
            return 'No patterns identified yet'
        parts = []
        for p in patterns:
            avoid = f' — {p.how_to_avoid[:100]}' if p.how_to_avoid else ''
            parts.append(f"- {p.pattern_name} (impact: {p.impact_score}/10, seen {p.occurrences}x){avoid}")
        return '\n'.join(parts)
```

**Step 5: Update `app/services/argos/__init__.py` exports**

Add `CompanionContext` to the exports so routes can import it:

```python
from app.services.argos.core import ArgosService, argos_check, CompanionContext
```

**Step 6: Run test to verify it passes**

Run: `cd /home/warlock20/dev/investment-checklist && venv/bin/python unittests/test_argos_companion.py`
Expected: PASS

**Step 7: Commit**

```bash
git add app/services/argos/core.py app/services/argos/__init__.py unittests/test_argos_companion.py
git commit -m "feat: add companion methods to ArgosService (brief, chat, counter-evidence, wrapup)"
```

---

## Task 5: Companion API Routes

Add Flask routes for companion features: brief generation, live chat, counter-evidence, session wrap-up, and quick-capture.

**Files:**
- Create: `app/research_workflow/companion_routes.py`
- Modify: `app/research_workflow/__init__.py` (import new routes)
- Test: manual via browser (routes depend on Flask app context + DB)

**Step 1: Create companion routes**

Create `app/research_workflow/companion_routes.py`:

```python
"""
Research Companion Routes

API endpoints for companion features:
- POST /companion/<project_id>/brief — generate research brief
- POST /companion/<project_id>/ask — live companion chat
- POST /companion/<project_id>/counter-evidence — counter-evidence for a finding
- POST /companion/<project_id>/wrapup — session wrap-up
- POST /research/api/capture — quick-capture from bookmarklet
- GET  /companion/<project_id>/captures — list captures for a project
- POST /companion/<project_id>/captures/<capture_id>/assign — assign capture to step
- POST /companion/<project_id>/captures/<capture_id>/dismiss — dismiss capture
"""

import logging
from flask import request
from flask_login import current_user, login_required
from app import db
from app.models.research import ResearchProject
from app.models.research_capture import ResearchCapture
from app.research_workflow import research_workflow_bp
from app.services.argos.core import ArgosService
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_success, json_error, json_unauthorized, json_validation_error
from app.utils.auth_utils import get_user_resource_or_403
from app.utils.db_utils import safe_commit, safe_add_and_commit

logger = logging.getLogger(__name__)


# =========================================================================
# Research Brief
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/brief', methods=['POST'])
@login_required
def companion_brief(project_id):
    """Generate a pre-session research brief."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)
    step_index = request.json.get('step_index', project.current_step_index)

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        brief = argos.generate_brief(context)
        return json_success('Brief generated', data={'brief': brief})
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Live Companion Chat
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/ask', methods=['POST'])
@login_required
def companion_ask(project_id):
    """Ask the companion a question during research."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    user_question = data.get('question', '').strip()
    conversation_history = data.get('conversation_history', [])
    step_index = data.get('step_index', project.current_step_index)

    if not user_question:
        return json_validation_error('Question is required')

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        answer = argos.ask_companion(context, user_question, conversation_history)
        return json_success('Answer generated', data={'answer': answer})
    except Exception as e:
        logger.error(f"Companion chat failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Counter-Evidence
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/counter-evidence', methods=['POST'])
@login_required
def companion_counter_evidence(project_id):
    """Generate counter-evidence for a finding."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    finding_text = data.get('finding_text', '').strip()
    research_question = data.get('research_question', '')
    step_index = data.get('step_index', project.current_step_index)

    if not finding_text:
        return json_validation_error('Finding text is required')

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        counter = argos.generate_counter_evidence(context, finding_text, research_question)
        return json_success('Counter-evidence generated', data={'counter_evidence': counter})
    except Exception as e:
        logger.error(f"Counter-evidence failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Session Wrap-Up
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/wrapup', methods=['POST'])
@login_required
def companion_wrapup(project_id):
    """Generate a session wrap-up summary."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    session_findings = data.get('session_findings', [])
    duration_minutes = data.get('duration_minutes', 0)
    counter_evidence = data.get('counter_evidence', [])
    step_index = data.get('step_index', project.current_step_index)

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        wrapup = argos.wrap_up_session(context, session_findings, duration_minutes, counter_evidence)

        # Store in session_history
        if not project.session_history:
            project.session_history = []
        project.session_history = project.session_history + [{
            'step_index': step_index,
            'duration_minutes': duration_minutes,
            'summary': wrapup,
            'timestamp': now_utc().isoformat(),
        }]
        safe_commit(db.session, 'session wrap-up')

        return json_success('Session wrapped up', data={'wrapup': wrapup})
    except Exception as e:
        logger.error(f"Session wrap-up failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Quick Capture (Bookmarklet API)
# =========================================================================

@research_workflow_bp.route('/research/api/capture', methods=['POST'])
@login_required
def quick_capture():
    """Capture a research finding from external source (bookmarklet)."""
    data = request.json or {}
    text = data.get('text', '').strip()
    url = data.get('url', '').strip() or None
    source_title = data.get('source_title', '').strip() or None
    project_id = data.get('project_id') if 'project_id' in data else None
    step_index = data.get('step_index') if 'step_index' in data else None

    if not text:
        return json_validation_error('Text is required')

    status = 'assigned' if project_id and step_index is not None else 'unassigned'

    capture = ResearchCapture(
        user_id=current_user.id,
        text=text,
        url=url,
        source_title=source_title,
        project_id=project_id,
        step_index=step_index,
        status=status,
        captured_at=now_utc(),
    )

    success = safe_add_and_commit(db.session, capture, 'quick capture')
    if success:
        return json_success('Captured', data={'capture': capture.to_dict()})
    return json_error('Failed to save capture', status_code=500)


@research_workflow_bp.route('/companion/<int:project_id>/captures', methods=['GET'])
@login_required
def list_captures(project_id):
    """List captures for a project (including unassigned ones)."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    captures = ResearchCapture.query.filter(
        ResearchCapture.user_id == current_user.id,
        db.or_(
            ResearchCapture.project_id == project_id,
            ResearchCapture.status == 'unassigned',
        )
    ).order_by(ResearchCapture.captured_at.desc()).all()

    return json_success('Captures loaded', data={'captures': [c.to_dict() for c in captures]})


@research_workflow_bp.route('/companion/<int:project_id>/captures/<int:capture_id>/assign', methods=['POST'])
@login_required
def assign_capture(project_id, capture_id):
    """Assign a capture to a specific project step."""
    capture = get_user_resource_or_403(ResearchCapture, capture_id, current_user.id)

    data = request.json or {}
    step_index = data.get('step_index')

    if step_index is None:
        return json_validation_error('step_index is required')

    capture.project_id = project_id
    capture.step_index = step_index
    capture.status = 'assigned'

    success = safe_commit(db.session, 'assign capture')
    if success:
        return json_success('Capture assigned', data={'capture': capture.to_dict()})
    return json_error('Failed to assign capture', status_code=500)


@research_workflow_bp.route('/companion/<int:project_id>/captures/<int:capture_id>/dismiss', methods=['POST'])
@login_required
def dismiss_capture(project_id, capture_id):
    """Dismiss a capture."""
    capture = get_user_resource_or_403(ResearchCapture, capture_id, current_user.id)
    capture.status = 'dismissed'

    success = safe_commit(db.session, 'dismiss capture')
    if success:
        return json_success('Capture dismissed')
    return json_error('Failed to dismiss capture', status_code=500)
```

**Step 2: Register routes in `app/research_workflow/__init__.py`**

Add at the end of the file (after existing route imports):

```python
from app.research_workflow import companion_routes  # noqa: F401
```

**Step 3: Commit**

```bash
git add app/research_workflow/companion_routes.py app/research_workflow/__init__.py
git commit -m "feat: add companion API routes (brief, chat, counter-evidence, capture)"
```

---

## Task 6: Bookmarklet JavaScript

Create the bookmarklet that captures selected text + URL and sends to the quick-capture API.

**Files:**
- Create: `app/static/js/bookmarklet.js`

**Step 1: Create bookmarklet source**

Create `app/static/js/bookmarklet.js`:

```javascript
/*
 * Research Companion — Quick Capture Bookmarklet
 *
 * Usage: Drag the bookmarklet link to your browser toolbar.
 * Click it on any page to capture selected text + URL.
 *
 * This file is the SOURCE. The actual bookmarklet is minified into a
 * javascript: URL. See the Research Clipboard page for the drag-and-drop link.
 */
(function() {
    var selectedText = window.getSelection().toString().trim();
    var pageTitle = document.title;
    var pageUrl = window.location.href;

    if (!selectedText) {
        selectedText = prompt('No text selected. Paste or type your finding:');
        if (!selectedText) return;
    }

    // Show a small confirmation popup
    var popup = document.createElement('div');
    popup.style.cssText = 'position:fixed;top:20px;right:20px;z-index:999999;background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px;font-family:system-ui;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:400px;';
    popup.innerHTML = '<div style="font-weight:600;margin-bottom:8px;">Saving to Research...</div>' +
        '<div style="font-size:12px;color:#a0a0a0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
        selectedText.substring(0, 100) + (selectedText.length > 100 ? '...' : '') + '</div>';
    document.body.appendChild(popup);

    // Send to capture API
    var API_BASE = '{{API_BASE}}';  // Replaced when serving the bookmarklet page
    fetch(API_BASE + '/research/api/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            text: selectedText,
            url: pageUrl,
            source_title: pageTitle
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            popup.innerHTML = '<div style="color:#4ade80;font-weight:600;">Captured!</div>' +
                '<div style="font-size:12px;color:#a0a0a0;margin-top:4px;">Saved to Research Clipboard</div>';
        } else {
            popup.innerHTML = '<div style="color:#f87171;font-weight:600;">Error</div>' +
                '<div style="font-size:12px;">' + (data.error || 'Unknown error') + '</div>';
        }
        setTimeout(function() { popup.remove(); }, 2000);
    })
    .catch(function(err) {
        popup.innerHTML = '<div style="color:#f87171;font-weight:600;">Error</div>' +
            '<div style="font-size:12px;">Could not reach server. Are you logged in?</div>';
        setTimeout(function() { popup.remove(); }, 3000);
    });
})();
```

**Step 2: Commit**

```bash
git add app/static/js/bookmarklet.js
git commit -m "feat: add bookmarklet source for quick-capture"
```

---

## Task 7: Warnings Endpoint + Companion CSS + Alert Partials

**Design Pivot:** Replace the floating chat widget with "invisible infrastructure" — warning banners and an enriched sidebar card. See design doc "UI Integration Strategy" section.

### 7a: Lightweight Warnings Endpoint

Add `GET /companion/<project_id>/warnings` — returns pattern warnings + journal insights from DB (zero token cost).

**Files:**
- Modify: `app/research_workflow/companion_routes.py` (add warnings endpoint)

The endpoint calls `_build_pattern_summary()`, `_build_journal_summary()`, `_build_mistake_summary()` via a new `get_warnings()` method on CompanionMixin. Returns structured JSON with warning items (title, message, severity, type).

### 7b: Companion CSS Rewrite

Replace the floating widget CSS with warning banner + sidebar card styles.

**Files:**
- Rewrite: `app/static/css/modules/_companion.css`

New styles:
- `.companion-alerts-card` — sidebar card for project dashboard
- `.companion-alert-item` — individual alert item (reuses `_warnings-widget.css` severity pattern)
- `.companion-banner` — top-of-page warning banner for research step pages
- `.companion-banner-item` — individual banner warning
- `.companion-banner-dismiss` — dismiss button

### 7c: Create Alert Partials

**Files:**
- Rewrite: `app/research_workflow/templates/partials/_companion_widget.html` → `_companion_alerts.html` (sidebar card partial)
- Create: `app/research_workflow/templates/partials/_companion_banner.html` (warning banner partial)

Both partials load warnings via AJAX from the warnings endpoint on page load.

---

## Task 8: Integrate Companion into All 4 Surfaces

### 8a: Project Dashboard — Sidebar Alerts Card

**Files:**
- Modify: `app/research_workflow/templates/project_dashboard.html`

Insert `{% include 'partials/_companion_alerts.html' %}` between Key Findings and Quick Actions cards (after line 290).

### 8b: Checklist Step — Warning Banner

**Files:**
- Modify: `app/research/templates/research_step.html`

Insert `{% include 'research_workflow/partials/_companion_banner.html' %}` at top of main content area.

### 8c: Free Research Step — Warning Banner

**Files:**
- Modify: `app/research_workflow/templates/free_research_step.html`

Insert `{% include 'partials/_companion_banner.html' %}` in existing warning banner area.

### 8d: Generic Step — Warning Banner

**Files:**
- Modify: `app/research_workflow/templates/execute_step.html`

Replace floating widget include with `{% include 'partials/_companion_banner.html' %}`.

---

## Task 9: Enrich Existing AI Tools with Companion Context

Modify the `ai_assist` route to inject companion context (journal insights, pattern warnings, mistake history) into AI responses.

**Files:**
- Modify: `app/research/ai_research_assistant_routes.py` (enrich `context_data` with companion context)
- Modify: `app/services/ai_research_assistant.py` (accept and use enriched context in prompts)

The existing `context_data = {'company_name': company_name}` gets extended with:
- `journal_insights` — past decisions for this company/sector
- `pattern_warnings` — behavioral patterns to watch for
- `mistake_history` — past mistakes in this company/sector

This enrichment is optional and only fires when `project_id` is available in the request.

---

## Task 10: Celery Tasks for Async Operations

Add Celery tasks for counter-evidence generation (runs async after finding is saved).

**Files:**
- Modify: `app/celery_tasks/tasks_research.py` (add companion tasks)

---

## Task 11: Integration Testing

End-to-end test of the companion flow: warnings endpoint, enriched AI tools, banner rendering.

**Files:**
- Create or update: `unittests/test_companion_integration.py`

---

## Summary

| Task | Status | What | Key Files |
|------|--------|------|-----------|
| 1 | DONE | Argos enrichment (journal + patterns) | `argos/config.py`, `argos/core.py` |
| 2 | DONE | Prompt templates | 4 YAML files |
| 3 | DONE | session_history field + use JournalEntry | `research.py` |
| 4 | DONE | Companion methods on ArgosService | `argos/companion.py` |
| 5 | DONE | API routes | `companion_routes.py` |
| 6 | DONE | Bookmarklet JS | `bookmarklet.js` |
| 7 | TODO | Warnings endpoint + CSS + partials | `companion_routes.py`, `_companion.css`, partials |
| 8 | TODO | Integrate into 4 surfaces | 4 template files |
| 9 | TODO | Enrich existing AI tools | `ai_research_assistant_routes.py` |
| 10 | TODO | Celery tasks | `tasks_research.py` |
| 11 | TODO | Integration testing | `test_companion_integration.py` |
