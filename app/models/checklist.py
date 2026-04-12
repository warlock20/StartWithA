# app/models/checklist.py

from app import db
from app.utils.time_utils import now_utc


class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(1000))
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )  # Link to User
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    # Relationships: A checklist has many items
    items = db.relationship(
        "ChecklistItem",
        backref="checklist",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Checklist {self.name}>"


class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)  # Detailed description for the item
    checklist_id = db.Column(
        db.Integer, db.ForeignKey("checklist.id"), nullable=False
    )  # Link to Checklist
    parent_id = db.Column(
        db.Integer, db.ForeignKey("checklist_item.id"), nullable=True
    )  # For sub-items
    order = db.Column(db.Integer, default=0)  # To maintain order

    # If this field is populated, it indicates the item can leverage LLM analysis
    # and this text can be used as the basis for the LLM query
    llm_prompt = db.Column(db.Text, nullable=True, default=None)

    # Relationship: A checklist item can have sub-items (children)
    children = db.relationship(
        "ChecklistItem",
        backref=db.backref("parent", remote_side=[id]),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChecklistItem {self.text[:30]}...>"


class QuestionBankItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # The text of the reusable question
    text = db.Column(db.Text, nullable=False)

    # An optional, reusable LLM prompt for this question
    llm_prompt = db.Column(db.Text, nullable=True)

    # Foreign key to sector - can be null for general questions
    sector_id = db.Column(db.Integer, db.ForeignKey("sector.id"), nullable=True, index=True)

    # Optional categorization (e.g. 'moat', 'risks', 'valuation', 'management')
    category = db.Column(db.String(100), nullable=True)

    # Track origin from a research project (nullable, SET NULL on project delete)
    source_project_id = db.Column(
        db.Integer,
        db.ForeignKey("research_project.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Usage tracking
    times_used = db.Column(db.Integer, nullable=False, default=0)
    last_used_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    # Relationships
    sector = db.relationship("Sector", backref="question_bank_items")
    source_project = db.relationship("ResearchProject", backref="question_bank_items")

    def __repr__(self):
        return f"<QuestionBankItem {self.text[:50]}...>"


class DestinationCheckpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this checkpoint to a specific Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this checkpoint to the User who created it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    target_date = db.Column(db.Date, nullable=False, index=True)
    metric = db.Column(
        db.String(200), nullable=False
    )  # E.g., "Quarterly Revenue", "EPS", "Product Launch"
    expectation = db.Column(
        db.Text, nullable=False
    )  # E.g., ">$5 Billion", "Successful and on time"

    # This will be updated by the user later
    status = db.Column(
        db.String(30), nullable=False, default="Active"
    )  # E.g., 'Active', 'Met', 'Not Met'
    description = db.Column(db.Text, nullable=True)  # Narrative thesis context for LLM automation
    outcome_notes = db.Column(db.Text, nullable=True)  # User's analysis of the outcome

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def __repr__(self):
        return f"<DestinationCheckpoint {self.metric} for Company {self.company_id}>"


class DocumentImport(db.Model):
    """
    Track document imports for checklist creation
    """
    __tablename__ = 'document_imports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # File information
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # pdf, docx, txt
    file_size = db.Column(db.Integer)  # Size in bytes
    file_path = db.Column(db.String(500))  # Stored file path

    # Processing information
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, completed, failed
    llm_provider = db.Column(db.String(50))  # openai, gemini
    processing_approach = db.Column(db.String(50))  # immediate, interactive

    # Extracted content
    raw_text = db.Column(db.Text)
    processed_items = db.Column(db.JSON)  # Structured checklist items from LLM

    # Results
    suggested_name = db.Column(db.String(200))
    suggested_description = db.Column(db.Text)
    created_checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'))

    # Metadata
    processing_time = db.Column(db.Float)  # Processing time in seconds
    error_message = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='document_imports')
    created_checklist = db.relationship('Checklist', backref='document_import', uselist=False)

    def __repr__(self):
        return f'<DocumentImport {self.filename} - {self.status}>'
