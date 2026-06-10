# Investment Checklist Platform
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
Bias Check Result Models

Stores cognitive bias analysis results for investment theses.
Based on Charlie Munger's "Psychology of Human Misjudgment" framework.

Purpose:
- Track bias patterns in user research over time
- Correlate bias scores with investment outcomes (via Argos)
- Provide personalized insights about recurring bias patterns
"""

from app import db
from app.utils.time_utils import now_utc


class BiasCheckResult(db.Model):
    """
    Store cognitive bias analysis results for a research project.

    Each record represents one bias check run on a project's combined
    research text (all step notes, thesis, etc.).

    Used for:
    - Displaying bias check results in the UI
    - Tracking bias patterns over time
    - Argos correlation with investment outcomes
    """
    __tablename__ = 'bias_check_result'

    id = db.Column(db.Integer, primary_key=True)

    # Links
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=False, index=True)

    # Overall scores
    overall_score = db.Column(db.Integer, nullable=False)  # 0-100 (100 = no concerns)
    overall_level = db.Column(db.String(20), nullable=False)  # 'low', 'moderate', 'high'
    excitement_score = db.Column(db.Integer, nullable=False)  # 0-100 (enthusiasm level)

    # Balance assessment
    balance_assessment = db.Column(db.Text, nullable=True)

    # Detected biases (JSON array)
    # Each: {type, severity, detected, summary, evidence[], suggestion, caveat}
    biases_detected = db.Column(db.JSON, nullable=False, default=list)

    # Strengths (JSON array of strings)
    strengths = db.Column(db.JSON, nullable=True, default=list)

    # Meta statistics
    word_count = db.Column(db.Integer, nullable=True)
    bullish_points = db.Column(db.Integer, nullable=True)
    bearish_points = db.Column(db.Integer, nullable=True)
    risks_acknowledged = db.Column(db.Integer, nullable=True)
    certainty_phrases = db.Column(db.Integer, nullable=True)
    superlatives = db.Column(db.Integer, nullable=True)

    # AI metadata
    tokens_used = db.Column(db.Integer, nullable=True)
    model_used = db.Column(db.String(50), nullable=True)
    prompt_version = db.Column(db.String(20), nullable=True, default='1.0')

    # User feedback
    feedback = db.Column(db.String(20), nullable=True)  # 'helpful', 'not_helpful'
    feedback_at = db.Column(db.DateTime, nullable=True)

    # For Argos correlation (populated later when outcome is known)
    investment_outcome = db.Column(db.String(20), nullable=True)  # 'win', 'loss', 'pending'
    return_percentage = db.Column(db.Float, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('bias_checks', lazy='dynamic'))
    project = db.relationship('ResearchProject', backref=db.backref('bias_checks', lazy='dynamic'))

    def __repr__(self):
        return f'<BiasCheckResult {self.id} project={self.project_id} score={self.overall_score}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'overall_score': self.overall_score,
            'overall_level': self.overall_level,
            'excitement_score': self.excitement_score,
            'balance_assessment': self.balance_assessment,
            'biases': self.biases_detected,
            'strengths': self.strengths or [],
            'meta': {
                'word_count': self.word_count,
                'bullish_points': self.bullish_points,
                'bearish_points': self.bearish_points,
                'risks_acknowledged': self.risks_acknowledged,
                'certainty_phrases': self.certainty_phrases,
                'superlatives': self.superlatives,
            },
            'tokens_used': self.tokens_used,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def mark_helpful(self):
        """Mark this result as helpful."""
        self.feedback = 'helpful'
        self.feedback_at = now_utc()

    def mark_not_helpful(self):
        """Mark this result as not helpful."""
        self.feedback = 'not_helpful'
        self.feedback_at = now_utc()

    @property
    def biases_with_concerns(self):
        """Get only biases that were detected (severity != 'none')."""
        return [b for b in (self.biases_detected or []) if b.get('detected') and b.get('severity') != 'none']

    @property
    def high_severity_count(self):
        """Count of high severity biases."""
        return len([b for b in self.biases_with_concerns if b.get('severity') == 'high'])

    @property
    def medium_severity_count(self):
        """Count of medium severity biases."""
        return len([b for b in self.biases_with_concerns if b.get('severity') == 'medium'])

    @classmethod
    def get_latest_for_project(cls, project_id):
        """Get the most recent bias check for a project."""
        return cls.query.filter_by(project_id=project_id).order_by(cls.created_at.desc()).first()

    @classmethod
    def get_user_average_score(cls, user_id):
        """Get average bias check score for a user."""
        from sqlalchemy import func
        result = cls.query.filter_by(user_id=user_id).with_entities(
            func.avg(cls.overall_score).label('avg_score')
        ).first()
        return round(result.avg_score, 1) if result and result.avg_score else None

    @classmethod
    def get_user_bias_patterns(cls, user_id, limit=10):
        """
        Get most common bias patterns for a user.

        Returns dict of bias_type -> {count, avg_severity_score}
        """
        results = cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).limit(limit).all()

        patterns = {}
        for result in results:
            for bias in result.biases_with_concerns:
                bias_type = bias.get('type')
                if bias_type not in patterns:
                    patterns[bias_type] = {'count': 0, 'severities': []}

                patterns[bias_type]['count'] += 1
                severity_score = {'high': 3, 'medium': 2, 'low': 1}.get(bias.get('severity'), 0)
                patterns[bias_type]['severities'].append(severity_score)

        # Calculate average severity
        for bias_type, data in patterns.items():
            if data['severities']:
                data['avg_severity'] = sum(data['severities']) / len(data['severities'])
            else:
                data['avg_severity'] = 0
            del data['severities']

        return patterns
