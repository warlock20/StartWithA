"""
Thesis Analysis Service

Uses AI to analyze investment theses for quality, identify weaknesses,
and provide actionable suggestions for improvement.

Features:
- Thesis quality scoring (0-100)
- Weakness identification
- Risk flag detection
- Suggested questions to consider
- Comparison to common investing pitfalls

Usage:
    from app.services.thesis_analysis import ThesisAnalyzer
    
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze_thesis(
        thesis="I believe NVDA will grow because AI is the future...",
        company_name="NVIDIA",
        ticker="NVDA",
        sector="Technology"
    )
    
    print(f"Quality Score: {result.quality_score}")
    print(f"Weaknesses: {result.weaknesses}")
"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from app.services.ai.prompt_service import get_intelligence_prompt

logger = logging.getLogger(__name__)


@dataclass
class ThesisAnalysisResult:
    """Result of thesis analysis"""
    quality_score: int  # 0-100
    quality_grade: str  # A, B, C, D, F
    summary: str  # Brief assessment
    
    # Detailed analysis
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    
    # Actionable suggestions
    suggested_questions: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)
    
    # Bias detection
    detected_biases: List[Dict[str, str]] = field(default_factory=list)
    
    # Metadata
    word_count: int = 0
    has_valuation: bool = False
    has_risks: bool = False
    has_catalysts: bool = False
    has_exit_criteria: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        return {
            'quality_score': self.quality_score,
            'quality_grade': self.quality_grade,
            'summary': self.summary,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'risk_flags': self.risk_flags,
            'suggested_questions': self.suggested_questions,
            'missing_elements': self.missing_elements,
            'detected_biases': self.detected_biases,
            'word_count': self.word_count,
            'has_valuation': self.has_valuation,
            'has_risks': self.has_risks,
            'has_catalysts': self.has_catalysts,
            'has_exit_criteria': self.has_exit_criteria,
        }


class ThesisAnalyzer:
    """
    Analyzes investment theses using AI.
    
    Provides structured feedback on thesis quality, identifies
    weaknesses, and suggests improvements.
    """
    
    # Keywords for element detection (used as fallback)
    VALUATION_KEYWORDS = [
        'pe ratio', 'p/e', 'price to earnings', 'valuation', 'multiple',
        'dcf', 'intrinsic value', 'fair value', 'undervalued', 'overvalued',
        'price target', 'ev/ebitda', 'price to sales', 'book value'
    ]
    
    RISK_KEYWORDS = [
        'risk', 'downside', 'concern', 'threat', 'competition', 'competitor',
        'regulatory', 'recession', 'debt', 'leverage', 'challenge', 'weakness',
        'bearish', 'negative', 'worry', 'afraid', 'uncertain'
    ]
    
    CATALYST_KEYWORDS = [
        'catalyst', 'upcoming', 'launch', 'release', 'earnings', 'announcement',
        'acquisition', 'merger', 'expansion', 'new product', 'guidance',
        'event', 'trigger', 'driver', 'timeline'
    ]
    
    EXIT_KEYWORDS = [
        'exit', 'sell when', 'would sell', 'stop loss', 'target price',
        'take profit', 'position size', 'time horizon', 'hold until',
        'thesis breaks', 'invalidate'
    ]
    
    # Common investing biases to detect
    BIAS_PATTERNS = {
        'confirmation_bias': {
            'patterns': ['only looked at', 'ignored', 'didnt consider', 'focus on positive'],
            'description': 'May be seeking information that confirms existing beliefs'
        },
        'recency_bias': {
            'patterns': ['recent performance', 'just announced', 'lately', 'this quarter'],
            'description': 'May be overweighting recent events'
        },
        'narrative_fallacy': {
            'patterns': ['story', 'believe in', 'vision', 'revolutionary', 'game changer'],
            'description': 'May be attracted to compelling narrative over fundamentals'
        },
        'anchoring': {
            'patterns': ['used to trade at', 'was at', 'down from', 'historically'],
            'description': 'May be anchored to past prices'
        },
        'herd_mentality': {
            'patterns': ['everyone is buying', 'popular', 'trending', 'buzz', 'hype'],
            'description': 'May be following the crowd'
        }
    }
    
    def __init__(self):
        self._ai_service = None
    
    @property
    def ai_service(self):
        """Lazy load AI service"""
        if self._ai_service is None:
            try:
                from app.services.ai.ai_service import get_ai_service
                self._ai_service = get_ai_service()
            except ImportError:
                logger.warning("AI service not available")
                self._ai_service = None
        return self._ai_service
    
    def analyze_thesis(
        self,
        thesis: str,
        company_name: Optional[str] = None,
        ticker: Optional[str] = None,
        sector: Optional[str] = None,
        expected_return: Optional[float] = None,
        expected_timeframe: Optional[int] = None,
        confidence_score: Optional[int] = None
    ) -> ThesisAnalysisResult:
        """
        Analyze an investment thesis.
        
        Args:
            thesis: The investment thesis text
            company_name: Name of the company (optional)
            ticker: Stock ticker (optional)
            sector: Company sector (optional)
            expected_return: Expected return % (optional)
            expected_timeframe: Expected timeframe in months (optional)
            confidence_score: User's confidence 1-10 (optional)
        
        Returns:
            ThesisAnalysisResult with detailed analysis
        """
        if not thesis or len(thesis.strip()) < 10:
            return ThesisAnalysisResult(
                quality_score=0,
                quality_grade='F',
                summary='No thesis provided or thesis too short.',
                weaknesses=['Thesis is empty or too short to analyze'],
                word_count=len(thesis.split()) if thesis else 0
            )
        
        word_count = len(thesis.split())
        thesis_lower = thesis.lower()
        
        # Detect basic elements
        has_valuation = any(kw in thesis_lower for kw in self.VALUATION_KEYWORDS)
        has_risks = any(kw in thesis_lower for kw in self.RISK_KEYWORDS)
        has_catalysts = any(kw in thesis_lower for kw in self.CATALYST_KEYWORDS)
        has_exit_criteria = any(kw in thesis_lower for kw in self.EXIT_KEYWORDS)
        
        # Detect potential biases
        detected_biases = self._detect_biases(thesis_lower)
        
        # Try AI analysis first
        if self.ai_service and self.ai_service.is_available():
            try:
                ai_result = self._analyze_with_ai(
                    thesis=thesis,
                    company_name=company_name,
                    ticker=ticker,
                    sector=sector,
                    expected_return=expected_return,
                    expected_timeframe=expected_timeframe,
                    confidence_score=confidence_score
                )
                
                # Merge AI results with local detection
                ai_result.word_count = word_count
                ai_result.has_valuation = ai_result.has_valuation or has_valuation
                ai_result.has_risks = ai_result.has_risks or has_risks
                ai_result.has_catalysts = ai_result.has_catalysts or has_catalysts
                ai_result.has_exit_criteria = ai_result.has_exit_criteria or has_exit_criteria
                
                # Add detected biases if AI didn't find them
                if not ai_result.detected_biases:
                    ai_result.detected_biases = detected_biases
                
                return ai_result
                
            except Exception as e:
                logger.warning(f"AI thesis analysis failed, using fallback: {e}")
        
        # Fallback to rule-based analysis
        return self._analyze_rule_based(
            thesis=thesis,
            word_count=word_count,
            has_valuation=has_valuation,
            has_risks=has_risks,
            has_catalysts=has_catalysts,
            has_exit_criteria=has_exit_criteria,
            detected_biases=detected_biases,
            expected_return=expected_return,
            confidence_score=confidence_score
        )
    
    def _analyze_with_ai(
        self,
        thesis: str,
        company_name: Optional[str],
        ticker: Optional[str],
        sector: Optional[str],
        expected_return: Optional[float],
        expected_timeframe: Optional[int],
        confidence_score: Optional[int]
    ) -> ThesisAnalysisResult:
        """Analyze thesis using AI service"""
        
        # Build context
        context_parts = []
        if company_name:
            context_parts.append(f"Company: {company_name}")
        if ticker:
            context_parts.append(f"Ticker: {ticker}")
        if sector:
            context_parts.append(f"Sector: {sector}")
        if expected_return:
            context_parts.append(f"Expected Return: {expected_return}%")
        if expected_timeframe:
            context_parts.append(f"Timeframe: {expected_timeframe} months")
        if confidence_score:
            context_parts.append(f"Investor Confidence: {confidence_score}/10")

        context = "\n".join(context_parts) if context_parts else "No additional context provided"

        # Use YAML-based prompt
        prompt = get_intelligence_prompt(
            'thesis_analysis_simple',
            context_info=context,
            thesis_text=thesis
        )

        try:
            response = self.ai_service.generate_json(prompt)
            
            # Extract and validate response
            quality_score = int(response.get('quality_score', 50))
            quality_score = max(0, min(100, quality_score))  # Clamp to 0-100
            
            return ThesisAnalysisResult(
                quality_score=quality_score,
                quality_grade=self._score_to_grade(quality_score),
                summary=response.get('summary', 'Analysis complete.'),
                strengths=response.get('strengths', []),
                weaknesses=response.get('weaknesses', []),
                risk_flags=response.get('risk_flags', []),
                suggested_questions=response.get('suggested_questions', []),
                missing_elements=response.get('missing_elements', []),
                detected_biases=response.get('detected_biases', []),
                has_valuation=response.get('has_valuation', False),
                has_risks=response.get('has_risks', False),
                has_catalysts=response.get('has_catalysts', False),
                has_exit_criteria=response.get('has_exit_criteria', False),
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            raise
    
    def _analyze_rule_based(
        self,
        thesis: str,
        word_count: int,
        has_valuation: bool,
        has_risks: bool,
        has_catalysts: bool,
        has_exit_criteria: bool,
        detected_biases: List[Dict[str, str]],
        expected_return: Optional[float],
        confidence_score: Optional[int]
    ) -> ThesisAnalysisResult:
        """Fallback rule-based analysis when AI is unavailable"""
        
        # Calculate score based on elements
        score = 40  # Base score
        
        # Word count scoring
        if word_count >= 200:
            score += 15
        elif word_count >= 100:
            score += 10
        elif word_count >= 50:
            score += 5
        
        # Element scoring
        if has_valuation:
            score += 15
        if has_risks:
            score += 10
        if has_catalysts:
            score += 10
        if has_exit_criteria:
            score += 10
        
        # Penalty for biases
        score -= len(detected_biases) * 3
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Build feedback
        strengths = []
        weaknesses = []
        missing_elements = []
        suggested_questions = []
        risk_flags = []
        
        if word_count >= 100:
            strengths.append("Thesis has good detail and depth")
        elif word_count < 50:
            weaknesses.append("Thesis is quite brief - consider adding more detail")
        
        if has_valuation:
            strengths.append("Includes valuation considerations")
        else:
            missing_elements.append("Valuation analysis (PE ratio, DCF, price target)")
            suggested_questions.append("What is the fair value of this company?")
        
        if has_risks:
            strengths.append("Acknowledges risks and challenges")
        else:
            missing_elements.append("Risk assessment")
            suggested_questions.append("What could go wrong with this investment?")
            risk_flags.append("No risks mentioned - every investment has risks")
        
        if has_catalysts:
            strengths.append("Identifies potential catalysts")
        else:
            missing_elements.append("Catalysts or triggers")
            suggested_questions.append("What events could drive the stock price?")
        
        if has_exit_criteria:
            strengths.append("Has exit strategy or criteria")
        else:
            missing_elements.append("Exit criteria")
            suggested_questions.append("Under what conditions would you sell?")
        
        # Check for unrealistic expectations
        if expected_return and expected_return > 50:
            risk_flags.append(f"Expected return of {expected_return}% is very aggressive")
            suggested_questions.append("Is this return expectation realistic based on historical data?")
        
        if confidence_score and confidence_score >= 9 and not has_risks:
            risk_flags.append("Very high confidence without documented risks - possible overconfidence")
        
        # Add bias warnings
        for bias in detected_biases:
            risk_flags.append(f"Possible {bias['bias_type'].replace('_', ' ')}: {bias['description']}")
        
        summary = self._generate_summary(score, has_valuation, has_risks, has_catalysts, has_exit_criteria)
        
        return ThesisAnalysisResult(
            quality_score=score,
            quality_grade=self._score_to_grade(score),
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            risk_flags=risk_flags,
            suggested_questions=suggested_questions,
            missing_elements=missing_elements,
            detected_biases=detected_biases,
            word_count=word_count,
            has_valuation=has_valuation,
            has_risks=has_risks,
            has_catalysts=has_catalysts,
            has_exit_criteria=has_exit_criteria,
        )
    
    def _detect_biases(self, thesis_lower: str) -> List[Dict[str, str]]:
        """Detect potential cognitive biases in thesis"""
        detected = []
        
        for bias_name, bias_info in self.BIAS_PATTERNS.items():
            for pattern in bias_info['patterns']:
                if pattern in thesis_lower:
                    detected.append({
                        'bias_type': bias_name,
                        'description': bias_info['description'],
                        'trigger': pattern
                    })
                    break  # Only add each bias once
        
        return detected
    
    def _score_to_grade(self, score: int) -> str:
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
    
    def _generate_summary(
        self,
        score: int,
        has_valuation: bool,
        has_risks: bool,
        has_catalysts: bool,
        has_exit_criteria: bool
    ) -> str:
        """Generate a summary based on score and elements"""
        
        elements_count = sum([has_valuation, has_risks, has_catalysts, has_exit_criteria])
        
        if score >= 90:
            return "Excellent thesis with comprehensive analysis covering key investment elements."
        elif score >= 80:
            return "Strong thesis with good reasoning. A few areas could be strengthened."
        elif score >= 70:
            missing = 4 - elements_count
            return f"Decent thesis but missing {missing} key element(s). Consider adding more depth."
        elif score >= 60:
            return "Basic thesis that needs more development. Several important areas are not addressed."
        else:
            return "Thesis needs significant improvement. Consider documenting your reasoning more thoroughly."
    
    def get_quick_assessment(self, thesis: str) -> Dict[str, Any]:
        """
        Get a quick assessment without full AI analysis.
        Useful for real-time feedback as user types.
        
        Args:
            thesis: The thesis text
            
        Returns:
            Dict with basic metrics
        """
        if not thesis:
            return {
                'word_count': 0,
                'has_minimum_length': False,
                'elements_detected': 0,
                'quick_score': 0
            }
        
        word_count = len(thesis.split())
        thesis_lower = thesis.lower()
        
        has_valuation = any(kw in thesis_lower for kw in self.VALUATION_KEYWORDS)
        has_risks = any(kw in thesis_lower for kw in self.RISK_KEYWORDS)
        has_catalysts = any(kw in thesis_lower for kw in self.CATALYST_KEYWORDS)
        has_exit_criteria = any(kw in thesis_lower for kw in self.EXIT_KEYWORDS)
        
        elements_detected = sum([has_valuation, has_risks, has_catalysts, has_exit_criteria])
        
        # Quick score calculation
        quick_score = min(100, (word_count // 5) + (elements_detected * 15))
        
        return {
            'word_count': word_count,
            'has_minimum_length': word_count >= 20,
            'elements_detected': elements_detected,
            'has_valuation': has_valuation,
            'has_risks': has_risks,
            'has_catalysts': has_catalysts,
            'has_exit_criteria': has_exit_criteria,
            'quick_score': quick_score
        }


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

_analyzer: Optional[ThesisAnalyzer] = None


def get_thesis_analyzer() -> ThesisAnalyzer:
    """Get singleton thesis analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ThesisAnalyzer()
    return _analyzer


def analyze_thesis(
    thesis: str,
    company_name: Optional[str] = None,
    ticker: Optional[str] = None,
    sector: Optional[str] = None,
    **kwargs
) -> ThesisAnalysisResult:
    """
    Convenience function to analyze a thesis.
    
    Args:
        thesis: The investment thesis text
        company_name: Company name (optional)
        ticker: Stock ticker (optional)
        sector: Sector (optional)
        **kwargs: Additional parameters
        
    Returns:
        ThesisAnalysisResult
    """
    analyzer = get_thesis_analyzer()
    return analyzer.analyze_thesis(
        thesis=thesis,
        company_name=company_name,
        ticker=ticker,
        sector=sector,
        **kwargs
    )


def get_quick_thesis_assessment(thesis: str) -> Dict[str, Any]:
    """
    Get quick thesis assessment for real-time feedback.
    
    Args:
        thesis: The thesis text
        
    Returns:
        Dict with basic metrics
    """
    analyzer = get_thesis_analyzer()
    return analyzer.get_quick_assessment(thesis)