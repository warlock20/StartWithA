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
    
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    ticker_symbol = db.Column(db.String(20), nullable=False, unique=True, index=True)
    # Add other company-specific fields if needed later (e.g., industry, exchange)

    # Relationship: A company can be part of many research sessions
    research_sessions = db.relationship('ResearchSession', backref='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.ticker_symbol} - {self.name}>'

class ResearchSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='in_progress') 
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)

    # Relationships:
    # The 'company' attribute is created by the backref from the Company model.
    # If your User model has a 'research_sessions' relationship with a backref='researcher',
    # then session.researcher would be available.

    # ADD/ENSURE THIS RELATIONSHIP FOR CHECKLIST:
    checklist = db.relationship('Checklist') 
    
    # You might also want a direct relationship to the User if not using a backref that names it 'user'
    # user = db.relationship('User') # If User model's backref isn't simply 'user'

    answers = db.relationship('ResearchAnswer', backref='session', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ResearchSession {self.id} for Company {self.company_id} using Checklist {self.checklist_id}>'

class ResearchAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer_text = db.Column(db.Text, nullable=True) # Textual answer from the user
    # file_path: For later, when we implement PDF uploads for specific questions
    # file_path = db.Column(db.String(300), nullable=True) 
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    research_session_id = db.Column(db.Integer, db.ForeignKey('research_session.id'), nullable=False)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)

    # Relationship to the specific checklist item this answer pertains to
    item = db.relationship('ChecklistItem') 

    def __repr__(self):
        return f'<ResearchAnswer {self.id} for Item {self.checklist_item_id} in Session {self.research_session_id}>'

# Optional: Add relationship from User to ResearchSession for easier access
# In the User model:
# research_sessions = db.relationship('ResearchSession', backref='researcher', lazy='dynamic')

# Optional: Add relationship from Checklist to ResearchSession
# In the Checklist model:
# research_sessions = db.relationship('ResearchSession', backref='applied_checklist', lazy='dynamic')    