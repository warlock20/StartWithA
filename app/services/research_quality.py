"""
Research Quality Calculator

Calculates a composite research quality score (0-100) based on:
- Completeness: How much of the checklist/template was completed
- Depth: Quality and thoroughness of answers
- Breadth: Variety of analysis types performed
- Time: Appropriate time invested (not too little, not excessive)
- Documents: Number of source documents analyzed

This is the foundation for Phase 1 - measuring research quality
so we can later correlate it with investment outcomes.

Usage:
    from app.services.research_quality import ResearchQualityCalculator, calculate_research_quality
    
    # Calculate for a research project
    score = calculate_research_quality(research_project_id=123)
    print(f"Quality Score: {score.overall_score} ({score.grade})")
    
    # Or use the calculator directly
    calculator = ResearchQualityCalculator()
    score = calculator.calculate_score(research_project_id=123)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app import db
from app.services.config_service import get_config

logger = logging.getLogger(__name__)


@dataclass
class ResearchQualityScore:
    """Research quality assessment result"""
    overall_score: float          # 0-100 composite score
    completeness_score: float     # How much of checklist completed
    depth_score: float            # Quality of answers
    breadth_score: float          # Variety of analysis types
    time_score: float             # Appropriate time invested
    document_score: float         # Document analysis depth
    
    grade: str                    # A, B, C, D, F
    improvement_tips: List[str] = field(default_factory=list)
    comparison_to_average: float = 0.0  # % vs user's average
    
    # Additional metadata
    questions_answered: int = 0
    questions_total: int = 0
    documents_analyzed: int = 0
    research_duration_minutes: int = 0
    
    # Research depth flags
    had_financial_analysis: bool = False
    had_competitive_analysis: bool = False
    had_management_review: bool = False
    had_valuation_model: bool = False


class ResearchQualityCalculator:
    """
    Calculate research quality scores.
    
    This is the foundation for Phase 1 - measuring research quality
    so we can later correlate it with outcomes.
    """
    
    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        'completeness': 0.25,
        'depth': 0.25,
        'breadth': 0.20,
        'time': 0.15,
        'documents': 0.15
    }

    def _get_thresholds(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get user-specific thresholds from their investment profile.
        Falls back to system defaults if not configured.
        """
        return {
            'min_questions_pct': get_config('min_questions_answered_pct', user_id, 70) / 100,
            'min_time_minutes': get_config('min_time_minutes', user_id, 30),
            'max_time_minutes': get_config('max_time_minutes', user_id, 480),
            'min_documents': get_config('min_documents_analyzed', user_id, 1),
            'ideal_documents': get_config('ideal_documents', user_id, 5),
            'min_answer_length': 50,         # Not user-configurable
            'good_answer_length': 200,       # Not user-configurable
            'excellent_answer_length': 500,  # Not user-configurable
        }
    
    def calculate_score(
        self,
        research_session_id: Optional[int] = None,
        research_project_id: Optional[int] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> ResearchQualityScore:
        """
        Calculate comprehensive research quality score.
        
        Can be called with either:
        - research_session_id (for checklist-based research)
        - research_project_id (for template-based research)
        - metrics dict (for manual/testing calculation)
        
        Args:
            research_session_id: ID of ChecklistAnalysis (checklist-based)
            research_project_id: ID of ResearchProject (template-based)
            metrics: Optional dict with pre-gathered metrics
            
        Returns:
            ResearchQualityScore with all component scores and tips
        """
        
        if metrics is None:
            metrics = self._gather_metrics(research_session_id, research_project_id)

        # Get user-specific thresholds
        thresholds = self._get_thresholds(metrics.get('user_id'))

        # Calculate component scores
        completeness = self._score_completeness(metrics, thresholds)
        depth = self._score_depth(metrics, thresholds)
        breadth = self._score_breadth(metrics, thresholds)
        time = self._score_time(metrics, thresholds)
        documents = self._score_documents(metrics, thresholds)
        
        # Weighted overall score
        overall = (
            completeness * self.WEIGHTS['completeness'] +
            depth * self.WEIGHTS['depth'] +
            breadth * self.WEIGHTS['breadth'] +
            time * self.WEIGHTS['time'] +
            documents * self.WEIGHTS['documents']
        )
        
        # Get improvement tips
        tips = self._generate_tips(completeness, depth, breadth, time, documents, metrics)
        
        # Get user's average for comparison
        user_avg = self._get_user_average(metrics.get('user_id'))
        comparison = ((overall - user_avg) / user_avg * 100) if user_avg > 0 else 0
        
        return ResearchQualityScore(
            overall_score=round(overall, 1),
            completeness_score=round(completeness, 1),
            depth_score=round(depth, 1),
            breadth_score=round(breadth, 1),
            time_score=round(time, 1),
            document_score=round(documents, 1),
            grade=self._score_to_grade(overall),
            improvement_tips=tips,
            comparison_to_average=round(comparison, 1),
            
            # Metadata
            questions_answered=metrics.get('questions_answered', 0),
            questions_total=metrics.get('questions_total', 0),
            documents_analyzed=metrics.get('documents_analyzed', 0),
            research_duration_minutes=metrics.get('time_spent_minutes', 0),
            
            # Depth flags
            had_financial_analysis=metrics.get('had_financial_analysis', False),
            had_competitive_analysis=metrics.get('had_competitive_analysis', False),
            had_management_review=metrics.get('had_management_review', False),
            had_valuation_model=metrics.get('had_valuation_model', False),
        )
    
    def _gather_metrics(
        self,
        session_id: Optional[int],
        project_id: Optional[int]
    ) -> Dict[str, Any]:
        """Gather metrics from database"""
        from app.models import (
            ResearchProject, WorkSession,
            CompanyDocument, ChecklistAnalysis, ChecklistAnswer
        )
        
        metrics = {
            'questions_answered': 0,
            'questions_total': 0,
            'answer_lengths': [],
            'satisfaction_ratings': [],
            'time_spent_minutes': 0,
            'documents_analyzed': 0,
            'ai_assists_used': 0,
            'had_financial_analysis': False,
            'had_competitive_analysis': False,
            'had_management_review': False,
            'had_valuation_model': False,
            'user_id': None,
            'company_id': None
        }
        
        # Gather from ChecklistAnalysis (checklist-based research)
        if session_id:
            analysis = ChecklistAnalysis.query.get(session_id)
            if analysis:
                metrics['user_id'] = analysis.user_id
                metrics['company_id'] = analysis.company_id

                # Get answers
                answers = ChecklistAnswer.query.filter_by(
                    checklist_analysis_id=session_id
                ).all()

                # Count questions from checklist
                if analysis.checklist:
                    metrics['questions_total'] = analysis.checklist.items.count()

                metrics['questions_answered'] = len([a for a in answers if a.answer_text])
                metrics['answer_lengths'] = [len(a.answer_text or '') for a in answers]

                # Check for document analysis in answers
                for answer in answers:
                    if answer.answer_text:
                        text_lower = answer.answer_text.lower()
                        if any(term in text_lower for term in ['financial', 'revenue', 'profit', 'margin', 'earnings']):
                            metrics['had_financial_analysis'] = True
                        if any(term in text_lower for term in ['competitor', 'market share', 'competitive']):
                            metrics['had_competitive_analysis'] = True
                        if any(term in text_lower for term in ['management', 'ceo', 'leadership', 'executive']):
                            metrics['had_management_review'] = True
                        if any(term in text_lower for term in ['valuation', 'dcf', 'multiple', 'fair value']):
                            metrics['had_valuation_model'] = True
        
        # Gather from ResearchProject (template-based)
        if project_id:
            project = ResearchProject.query.get(project_id)
            if project:
                metrics['user_id'] = project.user_id
                metrics['company_id'] = project.company_id
                
                # Time tracking - use total_hours_spent directly
                metrics['time_spent_minutes'] = int((project.total_hours_spent or 0) * 60)
                
                # ═══════════════════════════════════════════════════════════
                # Get ACTUAL questions from ChecklistAnalysis (not steps!)
                # ═══════════════════════════════════════════════════════════
                if project.company_id:
                    analyses = ChecklistAnalysis.query.filter_by(
                        user_id=project.user_id,
                        company_id=project.company_id,
                        status='completed'
                    ).all()
                    
                    total_questions = 0
                    total_answered = 0
                    all_answer_text = ""
                    
                    for analysis in analyses:
                        # Count total checklist items
                        if analysis.checklist:
                            total_questions += analysis.checklist.items.count()
                        
                        # Get answers
                        answers = ChecklistAnswer.query.filter_by(
                            checklist_analysis_id=analysis.id
                        ).all()
                        
                        for answer in answers:
                            if answer.answer_text:
                                total_answered += 1
                                metrics['answer_lengths'].append(len(answer.answer_text))
                                all_answer_text += " " + answer.answer_text
                            
                            # Collect satisfaction ratings
                            if answer.satisfaction_status:
                                metrics['satisfaction_ratings'].append(answer.satisfaction_status)
                    
                    metrics['questions_total'] = total_questions
                    metrics['questions_answered'] = total_answered
                    
                    # Check for analysis types in answers
                    text_lower = all_answer_text.lower()
                    if any(term in text_lower for term in ['financial', 'revenue', 'profit', 'margin', 'earnings', 'cash flow']):
                        metrics['had_financial_analysis'] = True
                    if any(term in text_lower for term in ['competitor', 'competitive', 'market share', 'moat']):
                        metrics['had_competitive_analysis'] = True
                    if any(term in text_lower for term in ['management', 'ceo', 'leadership', 'executive', 'founder']):
                        metrics['had_management_review'] = True
                    if any(term in text_lower for term in ['valuation', 'dcf', 'multiple', 'fair value', 'intrinsic']):
                        metrics['had_valuation_model'] = True
                
                # Also check step notes, thesis, and flags for depth indicators
                all_notes_text = ""
                if project.step_notes:
                    for note in project.step_notes.values():
                        if isinstance(note, str):
                            all_notes_text += " " + note
                        elif isinstance(note, dict):
                            all_notes_text += " " + str(note)
                
                if project.investment_thesis:
                    all_notes_text += " " + project.investment_thesis_text
                if project.green_flags:
                    all_notes_text += " " + " ".join(project.green_flags)
                if project.red_flags:
                    all_notes_text += " " + " ".join(project.red_flags)
                
                # Additional depth checks from notes
                note_lower = all_notes_text.lower()
                if any(term in note_lower for term in ['financial', 'revenue', 'profit', 'margin', 'earnings', 'cash flow']):
                    metrics['had_financial_analysis'] = True
                if any(term in note_lower for term in ['competitor', 'competitive', 'market share', 'moat']):
                    metrics['had_competitive_analysis'] = True
                if any(term in note_lower for term in ['management', 'ceo', 'leadership', 'executive', 'founder']):
                    metrics['had_management_review'] = True
                if any(term in note_lower for term in ['valuation', 'dcf', 'multiple', 'fair value', 'intrinsic']):
                    metrics['had_valuation_model'] = True
                
                # Count documents analyzed for the company
                if metrics['company_id']:
                    doc_count = CompanyDocument.query.filter_by(
                        company_id=metrics['company_id']
                    ).count()
                    metrics['documents_analyzed'] = doc_count
                
                return metrics
    def _score_completeness(self, metrics: Dict, thresholds: Dict) -> float:
        """Score based on % of questions answered"""
        if metrics['questions_total'] == 0:
            return 50.0  # Neutral if no questions defined

        pct = metrics['questions_answered'] / metrics['questions_total']

        if pct >= 0.9:
            return 100.0
        elif pct >= 0.7:
            return 70.0 + (pct - 0.7) * 150  # 70-100 range
        elif pct >= 0.5:
            return 50.0 + (pct - 0.5) * 100  # 50-70 range
        else:
            return pct * 100  # 0-50 range

    def _score_depth(self, metrics: Dict, thresholds: Dict) -> float:
        """Score based on answer quality (length as proxy)"""
        scores = []

        # Average answer length
        if metrics['answer_lengths']:
            avg_length = sum(metrics['answer_lengths']) / len(metrics['answer_lengths'])

            if avg_length >= thresholds['excellent_answer_length']:
                length_score = 100
            elif avg_length >= thresholds['good_answer_length']:
                length_score = 70 + (avg_length - thresholds['good_answer_length']) / 10
            elif avg_length >= thresholds['min_answer_length']:
                length_score = 40 + (avg_length - thresholds['min_answer_length']) / 5
            else:
                length_score = max(0, avg_length / thresholds['min_answer_length'] * 40)
            
            scores.append(min(100, length_score))
        
        # Satisfaction ratings
        if metrics['satisfaction_ratings']:
            sat_map = {
                'satisfied': 100, 
                'met': 100,
                'neutral': 60, 
                'informational': 60,
                'needs_attention': 40,
                'unsatisfied': 30,
                'not_met': 30
            }
            sat_scores = [sat_map.get(str(s).lower(), 50) for s in metrics['satisfaction_ratings']]
            scores.append(sum(sat_scores) / len(sat_scores))
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _score_breadth(self, metrics: Dict, thresholds: Dict) -> float:
        """Score based on variety of analysis types"""
        analysis_types = [
            metrics.get('had_financial_analysis', False),
            metrics.get('had_competitive_analysis', False),
            metrics.get('had_management_review', False),
            metrics.get('had_valuation_model', False),
        ]

        completed = sum(analysis_types)
        return (completed / len(analysis_types)) * 100

    def _score_time(self, metrics: Dict, thresholds: Dict) -> float:
        """Score based on time invested (with diminishing returns)"""
        minutes = metrics.get('time_spent_minutes', 0)

        if minutes == 0:
            return 30.0  # Low score if no time tracked
        elif minutes < thresholds['min_time_minutes']:
            # Too little time
            return (minutes / thresholds['min_time_minutes']) * 60
        elif minutes <= 120:
            # Good range (30-120 minutes)
            return 70 + ((minutes - 30) / 90) * 30
        elif minutes <= thresholds['max_time_minutes']:
            # Acceptable but long (120-480 minutes)
            return 80
        else:
            # Too much time (might indicate confusion)
            return 70

    def _score_documents(self, metrics: Dict, thresholds: Dict) -> float:
        """Score based on documents analyzed"""
        docs = metrics.get('documents_analyzed', 0)

        if docs == 0:
            return 30.0  # Penalty for no document analysis
        elif docs < thresholds['min_documents']:
            return 50.0
        elif docs < thresholds['ideal_documents']:
            return 50 + (docs / thresholds['ideal_documents']) * 50
        else:
            return 100.0
    
    def _generate_tips(
        self,
        completeness: float,
        depth: float,
        breadth: float,
        time: float,
        documents: float,
        metrics: Dict
    ) -> List[str]:
        """Generate actionable improvement tips"""
        tips = []
        
        if completeness < 70:
            unanswered = metrics['questions_total'] - metrics['questions_answered']
            if unanswered > 0:
                tips.append(f"Complete {unanswered} more checklist questions for better coverage")
        
        if depth < 60:
            tips.append("Add more detail to your answers - aim for at least 2-3 sentences per question")
        
        if breadth < 50:
            missing = []
            if not metrics.get('had_financial_analysis'):
                missing.append('financial analysis')
            if not metrics.get('had_competitive_analysis'):
                missing.append('competitive analysis')
            if not metrics.get('had_management_review'):
                missing.append('management review')
            if not metrics.get('had_valuation_model'):
                missing.append('valuation')
            if missing:
                tips.append(f"Consider adding: {', '.join(missing)}")
        
        if documents < 50:
            tips.append("Analyze more source documents (annual reports, earnings calls, etc.)")
        
        if time < 60 and metrics.get('time_spent_minutes', 0) < 30:
            tips.append("Spend more time on research - thorough analysis typically takes 1-2 hours")
        
        return tips[:3]  # Max 3 tips
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _get_user_average(self, user_id: Optional[int]) -> float:
        """Get user's historical average score"""
        if not user_id:
            return 70.0  # Default average
        
        from app.models.ai_intelligence import ResearchOutcome
        
        outcomes = ResearchOutcome.query.filter_by(user_id=user_id).all()
        if not outcomes:
            return 70.0
        
        scores = [o.research_quality_score for o in outcomes if o.research_quality_score]
        return sum(scores) / len(scores) if scores else 70.0


# ============================================================
# Convenience Functions
# ============================================================

def calculate_research_quality(
    research_session_id: Optional[int] = None,
    research_project_id: Optional[int] = None,
    metrics: Optional[Dict] = None
) -> ResearchQualityScore:
    """
    Calculate research quality score.
    
    Convenience function for easy access throughout the application.
    
    Args:
        research_session_id: ID of ResearchSession (checklist-based)
        research_project_id: ID of ResearchProject (template-based)
        metrics: Optional pre-gathered metrics dict
        
    Returns:
        ResearchQualityScore with all component scores
    """
    calculator = ResearchQualityCalculator()
    return calculator.calculate_score(
        research_session_id=research_session_id,
        research_project_id=research_project_id,
        metrics=metrics
    )


def get_research_quality_for_company(user_id: int, company_id: int) -> Optional[ResearchQualityScore]:
    """
    Get the most recent research quality score for a company.
    
    Looks for the latest completed research (session or project) and calculates score.
    
    Args:
        user_id: User ID
        company_id: Company ID
        
    Returns:
        ResearchQualityScore or None if no research found
    """
    from app.models import ChecklistAnalysis, ResearchProject

    # Check for research project first (more comprehensive)
    project = ResearchProject.query.filter_by(
        user_id=user_id,
        company_id=company_id,
        status='completed'
    ).order_by(ResearchProject.created_at.desc()).first()

    if project:
        return calculate_research_quality(research_project_id=project.id)

    # Fall back to checklist analysis
    analysis = ChecklistAnalysis.query.filter_by(
        user_id=user_id,
        company_id=company_id,
        status='completed'
    ).order_by(ChecklistAnalysis.created_at.desc()).first()

    if analysis:
        return calculate_research_quality(research_session_id=analysis.id)

    return None