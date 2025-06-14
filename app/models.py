# company_research_platform/app/models.py

from app import db # Import the db instance from app/__init__.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash # Import hashing functions
from flask_login import UserMixin # Import UserMixin
from app import login_manager # Import login_manager from app/__init__.py

favorite_companies = db.Table('favorite_companies',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('company_id', db.Integer, db.ForeignKey('company.id'), primary_key=True)
)

# User loader function required by Flask-Login
# This function is called to reload the user object from the user ID stored in the session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# The User class needs to inherit from UserMixin
class User(UserMixin, db.Model): # Add UserMixin here
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    uploaded_documents = db.relationship('CompanyDocument', backref='uploader', lazy='dynamic') 
    checklists = db.relationship('Checklist', backref='author', lazy='dynamic')
    research_sessions = db.relationship('ResearchSession', backref='researcher', lazy='dynamic')
    companies = db.relationship('Company', backref='creator', lazy='dynamic') 
    favorites = db.relationship('Company', secondary=favorite_companies, lazy='dynamic',
                                backref=db.backref('favorited_by', lazy='dynamic'))
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Ensure password_hash is not None before checking
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

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
    
    # If this field is populated, it indicates the item can leverage LLM analysis
    # and this text can be used as the basis for the LLM query
    llm_prompt = db.Column(db.Text, nullable=True, default=None) 
    
    # Relationship: A checklist item can have sub-items (children)
    children = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ChecklistItem {self.text[:30]}...>'
    
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    documents = db.relationship('CompanyDocument', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    summary = db.Column(db.Text, nullable=True) 
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(150), nullable=True)
    intrinsic_value = db.Column(db.BigInteger, nullable=True)    

    # Relationship: A company can be part of many research sessions
    research_sessions = db.relationship('ResearchSession', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    documents = db.relationship('CompanyDocument', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    # Optional: Define a unique constraint for (name, user_id) and (ticker_symbol, user_id)
    # if you want a user to not be able to add the same company multiple times,
    # but allow different users to potentially add companies with the same name/ticker.
    # __table_args__ = (
    #     db.UniqueConstraint('name', 'user_id', name='uq_user_company_name'),
    #     db.UniqueConstraint('ticker_symbol', 'user_id', name='uq_user_company_ticker'),
    # )
    
    def __repr__(self):
        return f'<Company {self.ticker_symbol} - {self.name}>'

class ResearchSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='in_progress') 
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    conclusion = db.Column(db.Text, nullable=True)
    
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
    satisfaction_status = db.Column(db.String(30), nullable=True, default='neutral')
    
    research_session_id = db.Column(db.Integer, db.ForeignKey('research_session.id'), nullable=False)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)

    # Relationship to the specific checklist item this answer pertains to
    item = db.relationship('ChecklistItem') 

    def __repr__(self):
        return f'<ResearchAnswer {self.id} for Item {self.checklist_item_id} in Session {self.research_session_id}>'

class CompanyDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this document to a Company
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    # Foreign key to link this document to the User who uploaded it
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    original_filename = db.Column(db.String(255), nullable=False) # Original name of the uploaded file
    # Stored file path, relative to a base upload directory.
    # Could be a unique generated filename or include subdirectories like company_id/
    stored_filename = db.Column(db.String(300), nullable=False, unique=True) 

    document_group = db.Column(db.String(100), nullable=False, index=True) # E.g., 'Annual Reports', 'Quarterly Reports', 'Analyst Transcripts'
    document_title = db.Column(db.String(255), nullable=True) # E.g., "2023 Annual Report", "Q4 2023 Earnings Call"
    document_date = db.Column(db.Date, nullable=True) # Publication date of the document, or period end date

    description = db.Column(db.Text, nullable=True) # Optional user description
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships (these will create the backrefs on Company and User)
    # company = db.relationship('Company', backref=db.backref('documents', lazy='dynamic')) # This is one way
    # uploader = db.relationship('User', backref=db.backref('uploaded_documents', lazy='dynamic')) # This is one way

    def __repr__(self):
        return f'<CompanyDocument {self.original_filename} for Company {self.company_id}>'