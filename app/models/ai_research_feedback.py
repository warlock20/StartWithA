# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
AI Research Feedback Models

Models for tracking AI research assistant interactions and user feedback.
Used to monitor quality, tune prompts, and provide data for future Argos analysis.

PRIVACY & GDPR COMPLIANCE:
--------------------------
This model stores user research data including questions, answers, and AI responses.

Data Collection Consent:
- Users who use AI Research Assistant features consent to data collection
- Data is used for quality improvement and personalized insights (Argos)
- Consent flow must be implemented before production launch (see TODO)

GDPR Compliance Requirements:
- Right to access: Users can view their AI interaction history
- Right to deletion: Users can request complete data deletion
- Right to export: Users can export their interaction data
- Data retention: Anonymize after 90 days, keep aggregated metrics only
- Purpose limitation: Data only used for prompt improvement and Argos correlation

Future Argos Requirement:
- Argos CANNOT work without user data (needs to correlate research → outcomes)
- user_id is REQUIRED for Argos to link sessions to portfolio performance
- Users who want Argos insights must consent to data collection

TODO Before Production:
- Implement consent modal on first AI feature use
- Add user settings toggle: "Enable AI Research Assistant"
- Implement data retention/cleanup job (90 days → anonymization)
- Add user data export endpoint
- Add user data deletion endpoint
- Privacy policy documentation
"""

from app import db
from app.utils.time_utils import now_utc


class AIResearchFeedback(db.Model):
    """
    Track AI Research Assistant interactions and user feedback.

    Stores:
    - User's question and answer
    - AI mode used (challenge/elaboration/factcheck)
    - AI response generated
    - User feedback (helpful/not_helpful/dismissed)
    - Context (company, research session)

    Purpose:
    - Quality monitoring (track helpful vs not helpful responses)
    - Prompt tuning (identify poorly performing prompts)
    - Cost tracking (tokens used per interaction)
    - Future Argos analysis (correlate challenged answers with outcomes)

    Privacy Note:
    - user_id is nullable for flexibility but ALWAYS stored when feature is used
    - Data collection is implicit consent when user uses AI features
    - Explicit consent flow required before production launch
    """
    __tablename__ = 'ai_research_feedback'

    id = db.Column(db.Integer, primary_key=True)

    # User who generated this interaction
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Context (nullable for reusability beyond research checklists)
    analysis_id = db.Column(db.Integer, db.ForeignKey('checklist_analysis.id'), nullable=True, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=True, index=True)
    company_name = db.Column(db.String(200), nullable=True)  # Denormalized for flexibility

    # AI mode used
    mode = db.Column(db.String(20), nullable=False, index=True)  # 'challenge', 'elaboration', 'factcheck'

    # User input
    question_text = db.Column(db.Text, nullable=False)  # The question being answered
    user_answer = db.Column(db.Text, nullable=False)    # User's original answer

    # AI output
    ai_response = db.Column(db.Text, nullable=False)    # AI-generated response
    tokens_used = db.Column(db.Integer, nullable=True)  # Approximate tokens for cost tracking

    # User feedback
    feedback = db.Column(db.String(20), nullable=True, index=True)  # 'helpful', 'not_helpful', 'dismissed', None
    feedback_at = db.Column(db.DateTime, nullable=True)  # When user provided feedback

    # Answer revision tracking (for future Argos correlation)
    answer_revised = db.Column(db.Boolean, default=False)  # Did user revise answer after AI challenge?
    revised_answer = db.Column(db.Text, nullable=True)     # New answer if revised

    # Metadata
    prompt_version = db.Column(db.String(20), nullable=True)  # Version of prompt template used
    provider = db.Column(db.String(20), nullable=True)        # 'gemini', 'claude', etc.
    model = db.Column(db.String(50), nullable=True)           # Specific model used

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('ai_research_feedback', lazy='dynamic'))
    analysis = db.relationship('ChecklistAnalysis', backref=db.backref('ai_feedback', lazy='dynamic'))
    item = db.relationship('ChecklistItem', backref=db.backref('ai_feedback', lazy='dynamic'))

    def __repr__(self):
        return f'<AIResearchFeedback {self.id} mode={self.mode} feedback={self.feedback}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'mode': self.mode,
            'question_text': self.question_text,
            'user_answer': self.user_answer,
            'ai_response': self.ai_response,
            'tokens_used': self.tokens_used,
            'feedback': self.feedback,
            'feedback_at': self.feedback_at.isoformat() if self.feedback_at else None,
            'answer_revised': self.answer_revised,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'company_name': self.company_name,
        }

    def mark_helpful(self):
        """Mark this interaction as helpful."""
        self.feedback = 'helpful'
        self.feedback_at = now_utc()

    def mark_not_helpful(self):
        """Mark this interaction as not helpful."""
        self.feedback = 'not_helpful'
        self.feedback_at = now_utc()

    def mark_dismissed(self):
        """Mark this interaction as dismissed."""
        self.feedback = 'dismissed'
        self.feedback_at = now_utc()

    def record_answer_revision(self, revised_answer_text: str):
        """Record that user revised their answer after AI feedback."""
        self.answer_revised = True
        self.revised_answer = revised_answer_text

    @property
    def is_feedback_provided(self) -> bool:
        """Check if user has provided any feedback."""
        return self.feedback is not None

    @property
    def is_helpful(self) -> bool:
        """Check if feedback was positive."""
        return self.feedback == 'helpful'

    @classmethod
    def get_helpfulness_rate(cls, mode=None, user_id=None):
        """
        Calculate helpfulness rate for quality monitoring.

        Args:
            mode: Optional mode filter ('challenge', 'elaboration', 'factcheck')
            user_id: Optional user filter

        Returns:
            Dict with total, helpful, not_helpful counts and rate
        """
        query = cls.query.filter(cls.feedback.isnot(None))

        if mode:
            query = query.filter_by(mode=mode)
        if user_id:
            query = query.filter_by(user_id=user_id)

        total_with_feedback = query.count()
        helpful_count = query.filter_by(feedback='helpful').count()
        not_helpful_count = query.filter_by(feedback='not_helpful').count()

        helpfulness_rate = (helpful_count / total_with_feedback * 100) if total_with_feedback > 0 else 0

        return {
            'total_with_feedback': total_with_feedback,
            'helpful': helpful_count,
            'not_helpful': not_helpful_count,
            'dismissed': total_with_feedback - helpful_count - not_helpful_count,
            'helpfulness_rate': round(helpfulness_rate, 1)
        }

    @classmethod
    def get_mode_usage_stats(cls, user_id=None):
        """
        Get usage statistics per mode.

        Args:
            user_id: Optional user filter

        Returns:
            Dict with usage counts per mode
        """
        query = cls.query
        if user_id:
            query = query.filter_by(user_id=user_id)

        from sqlalchemy import func
        results = query.with_entities(
            cls.mode,
            func.count(cls.id).label('count')
        ).group_by(cls.mode).all()

        return {mode: count for mode, count in results}
