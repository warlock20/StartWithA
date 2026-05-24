# app/models/background_task.py

from app import db
from app.utils.time_utils import now_utc


class BackgroundTask(db.Model):
    """Simple background task tracking for LLM operations"""
    id = db.Column(db.String(36), primary_key=True)  # UUID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    task_type = db.Column(db.String(50), nullable=False)  # 'competitor_analysis', etc.
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed

    # Task parameters
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), index=True)
    step_index = db.Column(db.Integer)

    # Results
    result = db.Column(db.Text)  # JSON string of results
    error_message = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='background_tasks')
    project = db.relationship('ResearchProject', backref='background_tasks')

    def __repr__(self):
        return f'<BackgroundTask {self.id} {self.task_type} {self.status}>'
