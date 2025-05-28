# company_research_platform/app/models.py

from app import db # Import the db instance from app/__init__.py
from datetime import datetime

# For now, a very simple User model. We'll expand this later.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    # In a real app, you'd have email, password_hash, etc.
    
    # Relationships: A user can have multiple checklists
    checklists = db.relationship('Checklist', backref='author', lazy='dynamic')
    # research_sessions = db.relationship('ResearchSession', backref='researcher', lazy='dynamic') # For later

    def __repr__(self):
        return f'<User {self.username}>'

class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Link to User
    
    # Relationships: A checklist has many items
    items = db.relationship('ChecklistItem', backref='checklist', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Checklist {self.name}>'

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False) # Link to Checklist
    
    parent_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=True) # For sub-items
    order = db.Column(db.Integer, default=0) # To maintain order

    # Relationships: A checklist item can have sub-items
    # 'remote_side=[id]' is used to clarify the self-referential relationship for SQLAlchemy
    children = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")

    # item_type = db.Column(db.String(50), default='text') # Future: 'text', 'number', 'file_prompt'

    def __repr__(self):
        return f'<ChecklistItem {self.text[:30]}...>'