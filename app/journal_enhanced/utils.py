from datetime import datetime, timedelta, date
from app import db
from app.models import (JournalEntry, ThesisEvolution, LearningNote,
                       JournalTemplate, Company)
import re
from collections import Counter

def extract_tags_from_content(content):
    """
    Extract hashtags from journal content.
    """
    pattern = r'#(\w+)'
    tags = re.findall(pattern, content)
    return list(set(tags))  # Remove duplicates

def get_related_entries(entry, limit=5):
    """
    Find related journal entries based on tags, company, and content similarity.
    """
    related = []
    
    # Same company entries
    if entry.company_id:
        company_entries = JournalEntry.query.filter(
            JournalEntry.company_id == entry.company_id,
            JournalEntry.id != entry.id,
            JournalEntry.user_id == entry.user_id
        ).order_by(JournalEntry.created_at.desc()).limit(limit).all()
        related.extend(company_entries)
    
    # Same tags entries
    if entry.tags:
        tag_entries = JournalEntry.query.filter(
            JournalEntry.tags.op('@>')(entry.tags),
            JournalEntry.id != entry.id,
            JournalEntry.user_id == entry.user_id
        ).limit(limit).all()
        related.extend(tag_entries)
    
    # Remove duplicates and limit
    seen = set()
    unique_related = []
    for e in related:
        if e.id not in seen:
            seen.add(e.id)
            unique_related.append(e)
            if len(unique_related) >= limit:
                break
    
    return unique_related

def get_review_queue(user_id):
    """
    Get learning notes and important entries due for review.
    """
    today = date.today()

    # Learning notes due for review
    learning_notes = LearningNote.query.filter(
        LearningNote.user_id == user_id,
        LearningNote.next_review_date <= today
    ).order_by(LearningNote.importance.desc()).all()

    # New entries that have never been reviewed (pending review)
    pending_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.last_reviewed.is_(None),
        JournalEntry.is_archived == False
    ).order_by(JournalEntry.created_at.desc()).all()

    # Starred entries not reviewed in 30+ days (excluding ones already in pending)
    starred_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.is_starred == True,
        JournalEntry.last_reviewed.isnot(None),  # Exclude never-reviewed entries (they're in pending)
        JournalEntry.last_reviewed < datetime.utcnow() - timedelta(days=30),
        JournalEntry.is_archived == False
    ).all()

    return {
        'learning_notes': learning_notes,
        'pending_entries': pending_entries,
        'starred_entries': starred_entries,
        'total_items': len(learning_notes) + len(pending_entries) + len(starred_entries)
    }

def update_thesis_version(user_id, company_id, new_thesis, trigger=None):
    """
    Create a new thesis version for a company.
    """
    # Mark current thesis as not current
    ThesisEvolution.query.filter_by(
        user_id=user_id,
        company_id=company_id,
        is_current=True
    ).update({'is_current': False})
    
    # Get the latest version number
    latest = ThesisEvolution.query.filter_by(
        user_id=user_id,
        company_id=company_id
    ).order_by(ThesisEvolution.version.desc()).first()
    
    new_version = (latest.version + 1) if latest else 1
    
    # Create new thesis version
    thesis_evolution = ThesisEvolution(
        user_id=user_id,
        company_id=company_id,
        version=new_version,
        thesis=new_thesis,
        change_trigger=trigger,
        is_current=True
    )
    
    db.session.add(thesis_evolution)
    
    try:
        db.session.commit()
        return thesis_evolution
    except Exception as e:
        db.session.rollback()
        print(f"Error updating thesis: {e}")
        return None

def calculate_next_review_date(learning_note):
    """
    Calculate next review date using spaced repetition algorithm.
    """
    # Simple spaced repetition: double the interval each time
    if learning_note.times_reviewed == 0:
        interval = 1
    elif learning_note.times_reviewed == 1:
        interval = 3
    elif learning_note.times_reviewed == 2:
        interval = 7
    elif learning_note.times_reviewed == 3:
        interval = 14
    elif learning_note.times_reviewed == 4:
        interval = 30
    else:
        interval = 60
    
    # Adjust based on importance
    if learning_note.importance >= 8:
        interval = int(interval * 0.7)  # Review important notes more frequently
    elif learning_note.importance <= 3:
        interval = int(interval * 1.5)  # Review less important notes less frequently
    
    return date.today() + timedelta(days=interval)

def search_journal(user_id, query, filters=None):
    """
    Search journal entries with various filters.
    """
    # Base query
    search = JournalEntry.query.filter_by(user_id=user_id, is_archived=False)
    
    # Text search in content and title
    if query:
        search_pattern = f'%{query}%'
        search = search.filter(
            db.or_(
                JournalEntry.content.ilike(search_pattern),
                JournalEntry.title.ilike(search_pattern),
                JournalEntry.key_insight.ilike(search_pattern)
            )
        )
    
    # Apply filters
    if filters:
        if filters.get('company_id'):
            search = search.filter_by(company_id=filters['company_id'])
        
        if filters.get('entry_type'):
            search = search.filter_by(entry_type=filters['entry_type'])
        
        if filters.get('sentiment'):
            search = search.filter_by(sentiment=filters['sentiment'])
        
        if filters.get('starred_only'):
            search = search.filter_by(is_starred=True)
        
        if filters.get('date_from'):
            search = search.filter(JournalEntry.created_at >= filters['date_from'])
        
        if filters.get('date_to'):
            search = search.filter(JournalEntry.created_at <= filters['date_to'])
        
        if filters.get('tags'):
            # Filter by tags (requires all specified tags)
            for tag in filters['tags']:
                search = search.filter(JournalEntry.tags.contains([tag]))
    
    # Order by relevance (most recent first for now)
    results = search.order_by(JournalEntry.created_at.desc()).all()
    
    return results

def get_journal_statistics(user_id):
    """
    Get statistics about journal usage.
    """
    total_entries = JournalEntry.query.filter_by(user_id=user_id).count()
    
    # Entries by type
    type_counts = db.session.query(
        JournalEntry.entry_type,
        db.func.count(JournalEntry.id)
    ).filter_by(user_id=user_id).group_by(JournalEntry.entry_type).all()
    
    # Most used tags
    all_tags = []
    entries_with_tags = JournalEntry.query.filter_by(user_id=user_id).filter(
        JournalEntry.tags.isnot(None)
    ).all()
    for entry in entries_with_tags:
        if entry.tags:
            all_tags.extend(entry.tags)
    
    tag_counts = Counter(all_tags).most_common(10)
    
    # Recent activity
    last_7_days = datetime.utcnow() - timedelta(days=7)
    recent_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.created_at >= last_7_days
    ).count()
    
    # Learning notes stats
    total_lessons = LearningNote.query.filter_by(user_id=user_id).count()

    # Pending reviews: Learning notes + Journal entries that have never been reviewed
    pending_learning_notes = LearningNote.query.filter(
        LearningNote.user_id == user_id,
        LearningNote.next_review_date <= date.today()
    ).count()

    pending_journal_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.last_reviewed.is_(None),
        JournalEntry.is_archived == False
    ).count()

    pending_reviews = pending_learning_notes + pending_journal_entries
    
    return {
        'total_entries': total_entries,
        'type_counts': dict(type_counts),
        'top_tags': tag_counts,
        'recent_entries': recent_entries,
        'total_lessons': total_lessons,
        'pending_reviews': pending_reviews
    }

def create_default_templates():
    """
    Create default journal templates for common use cases.
    """
    templates = [
        {
            'name': 'Earnings Call Notes',
            'entry_type': 'earnings_reaction',
            'description': 'Structured template for earnings call analysis',
            'prompts': [
                'What were the key financial metrics?',
                'What surprised you positively?',
                'What concerned you?',
                'How did management sound?',
                'What are the forward-looking statements?',
                'Action items after this call?'
            ]
        },
        {
            'name': 'Investment Thesis Update',
            'entry_type': 'thesis_update',
            'description': 'Track evolution of your investment thesis',
            'prompts': [
                'What has changed since last update?',
                'Current bull case (3-5 points)',
                'Current bear case (3-5 points)',
                'Key metrics to watch',
                'Conviction level (1-10) and why',
                'Position sizing thoughts'
            ]
        },
        {
            'name': 'Market Observation',
            'entry_type': 'market_thought',
            'description': 'Capture thoughts about market conditions',
            'prompts': [
                'What pattern or trend did you observe?',
                'What might this mean for your portfolio?',
                'Historical precedents?',
                'Contrarian view?',
                'Action items?'
            ]
        },
        {
            'name': 'Learning from Mistake',
            'entry_type': 'lesson_learned',
            'description': 'Document and learn from investment mistakes',
            'prompts': [
                'What was the mistake?',
                'What was your thought process at the time?',
                'What did you miss or misjudge?',
                'What would you do differently?',
                'How can you avoid this in future?',
                'What systematic change should you make?'
            ]
        }
    ]
    
    created_templates = []
    for template_data in templates:
        template = JournalTemplate.query.filter_by(
            name=template_data['name'],
            user_id=None  # System templates
        ).first()
        
        if not template:
            template = JournalTemplate(
                name=template_data['name'],
                entry_type=template_data['entry_type'],
                description=template_data['description'],
                prompts=template_data['prompts'],
                is_public=True
            )
            db.session.add(template)
            created_templates.append(template)
    
    if created_templates:
        try:
            db.session.commit()
            return created_templates
        except Exception as e:
            db.session.rollback()
            print(f"Error creating templates: {e}")
    
    return []