"""
Starter Content Service
Provides default templates, checklists, and content for new users during onboarding
"""

from app import db
from app.models import (
    KillChecklist, KillCriterion, ResearchTemplate,
    QuestionBankItem, ResearchProject
)
import logging

logger = logging.getLogger(__name__)


class StarterContentService:
    """Service for creating starter content during onboarding"""

    @staticmethod
    def create_starter_kill_checklist(user_id):
        """Create a basic kill checklist for new users"""
        try:
            # Create the kill checklist
            kill_checklist = KillChecklist(
                name="My First Kill Checklist",
                description="Essential filters to kill bad investment ideas quickly. Created during onboarding.",
                user_id=user_id,
                is_default=True
            )
            db.session.add(kill_checklist)
            db.session.flush()  # Get the ID

            # Add basic kill criteria
            basic_criteria = [
                {
                    "question": "Do I understand how this company makes money?",
                    "failure_reason": "If you can't explain the business model simply, you shouldn't invest.",
                    "help_text": "Can you explain their revenue streams in one sentence? If not, this is a red flag.",
                    "order": 1
                },
                {
                    "question": "Is the balance sheet healthy? (Low debt)",
                    "failure_reason": "High debt can kill companies during tough times.",
                    "help_text": "Look for debt-to-equity ratio below 0.5, or strong cash flow to service debt.",
                    "order": 2
                },
                {
                    "question": "Would I be comfortable holding this for 5 years?",
                    "failure_reason": "If you're not willing to hold long-term, you're probably speculating.",
                    "help_text": "Great investments should be companies you'd happily own for decades.",
                    "order": 3
                },
                {
                    "question": "Does management have a good track record?",
                    "failure_reason": "Poor management can destroy even great businesses.",
                    "help_text": "Look for honest communication, rational capital allocation, and past performance.",
                    "order": 4
                },
                {
                    "question": "Is the valuation reasonable?",
                    "failure_reason": "Even great companies can be terrible investments at the wrong price.",
                    "help_text": "Compare P/E, PEG ratio, and price-to-book with industry averages and historical norms.",
                    "order": 5
                }
            ]

            for criteria_data in basic_criteria:
                criterion = KillCriterion(
                    kill_checklist_id=kill_checklist.id,
                    question=criteria_data["question"],
                    failure_reason=criteria_data["failure_reason"],
                    help_text=criteria_data["help_text"],
                    order=criteria_data["order"],
                    times_evaluated=0,
                    times_failed=0
                )
                db.session.add(criterion)

            db.session.commit()
            logger.info(f"Created starter kill checklist for user {user_id}")
            return kill_checklist

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating starter kill checklist for user {user_id}: {e}")
            return None

    @staticmethod
    def create_starter_research_template(user_id):
        """Create a basic research template for new users"""
        try:
            # Create the research template
            template = ResearchTemplate(
                name="My First Research Template",
                description="Systematic research workflow for analyzing investment opportunities. Created during onboarding.",
                user_id=user_id,
                is_default=True,
                estimated_hours=3.5,
                workflow_steps=[
                    {
                        "name": "Business Model Analysis",
                        "description": "Understand how the company makes money and creates value",
                        "estimated_minutes": 30,
                        "order": 1,
                        "step_type": "analysis",
                        "questions": [
                            {
                                "text": "What are the company's main revenue streams?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "What is their competitive advantage (moat)?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "Who are their key customers and suppliers?",
                                "type": "text",
                                "required": True
                            }
                        ]
                    },
                    {
                        "name": "Competitive Position",
                        "description": "Analyze competitive advantages, threats, and market position",
                        "estimated_minutes": 45,
                        "order": 2,
                        "step_type": "analysis",
                        "questions": [
                            {
                                "text": "Who are the main competitors?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "What barriers to entry exist in this industry?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "How defensible is their market position?",
                                "type": "rating",
                                "scale": "1-10",
                                "required": True
                            }
                        ]
                    },
                    {
                        "name": "Financial Health Deep Dive",
                        "description": "Review financial statements, ratios, and cash flow",
                        "estimated_minutes": 60,
                        "order": 3,
                        "step_type": "financial_analysis",
                        "questions": [
                            {
                                "text": "What is the debt-to-equity ratio?",
                                "type": "number",
                                "required": True
                            },
                            {
                                "text": "What are the revenue growth trends over 5 years?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "How consistent are the profit margins?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "What is the return on equity (ROE)?",
                                "type": "number",
                                "required": True
                            }
                        ]
                    },
                    {
                        "name": "Management Quality Review",
                        "description": "Evaluate leadership, governance, and track record",
                        "estimated_minutes": 30,
                        "order": 4,
                        "step_type": "qualitative_analysis",
                        "questions": [
                            {
                                "text": "How long has current management been in place?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "What is their track record of capital allocation?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "How transparent and honest is their communication?",
                                "type": "rating",
                                "scale": "1-10",
                                "required": True
                            }
                        ]
                    },
                    {
                        "name": "Valuation Check",
                        "description": "Determine if the current price offers a good value",
                        "estimated_minutes": 45,
                        "order": 5,
                        "step_type": "valuation",
                        "questions": [
                            {
                                "text": "What is the current P/E ratio vs industry average?",
                                "type": "text",
                                "required": True
                            },
                            {
                                "text": "What price would represent fair value?",
                                "type": "number",
                                "required": True
                            },
                            {
                                "text": "What is your margin of safety at current price?",
                                "type": "text",
                                "required": True
                            }
                        ]
                    }
                ]
            )

            db.session.add(template)
            db.session.commit()
            logger.info(f"Created starter research template for user {user_id}")
            return template

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating starter research template for user {user_id}: {e}")
            return None

    @staticmethod
    def create_starter_question_bank(user_id):
        """Create starter questions for the user's question bank"""
        try:
            starter_questions = [
                # General questions
                {
                    "text": "What regulatory risks could impact this business?",
                    "sector": None,
                    "category": "Risk Analysis",
                    "llm_prompt": "Analyze potential regulatory changes that could affect this company's business model, revenue, or operations. Consider both existing regulations and potential future changes."
                },
                {
                    "text": "How cyclical is this business?",
                    "sector": None,
                    "category": "Business Model",
                    "llm_prompt": "Evaluate how sensitive this company's performance is to economic cycles. Consider revenue stability, customer behavior during recessions, and historical performance during downturns."
                },

                # Technology sector
                {
                    "text": "How fast is the technology becoming obsolete?",
                    "sector": "Technology",
                    "category": "Competitive Analysis",
                    "llm_prompt": "Assess the rate of technological change in this company's sector and how well-positioned they are to adapt or lead innovation."
                },
                {
                    "text": "What are the switching costs for customers?",
                    "sector": "Technology",
                    "category": "Competitive Moat",
                    "llm_prompt": "Analyze how difficult and expensive it would be for customers to switch to a competitor's product or service."
                },

                # Banking sector
                {
                    "text": "What is the bank's loan loss provision trend?",
                    "sector": "Banking",
                    "category": "Financial Health",
                    "llm_prompt": "Examine the bank's loan loss provisions over the past 5 years to understand credit quality and risk management."
                },
                {
                    "text": "How diversified are the revenue streams?",
                    "sector": "Banking",
                    "category": "Business Model",
                    "llm_prompt": "Analyze the bank's revenue breakdown between interest income, fees, trading, and other sources to assess diversification."
                },

                # Healthcare sector
                {
                    "text": "What is the drug pipeline and patent cliff exposure?",
                    "sector": "Healthcare",
                    "category": "Future Growth",
                    "llm_prompt": "Evaluate the company's drug development pipeline and assess risks from upcoming patent expirations."
                },
                {
                    "text": "How dependent is the company on government healthcare spending?",
                    "sector": "Healthcare",
                    "category": "Risk Analysis",
                    "llm_prompt": "Assess the company's exposure to changes in government healthcare policies, Medicare/Medicaid reimbursements, and regulatory changes."
                }
            ]

            for question_data in starter_questions:
                question = QuestionBankItem(
                    user_id=user_id,
                    text=question_data["text"],
                    sector=question_data["sector"],
                    category=question_data["category"],
                    llm_prompt=question_data["llm_prompt"],
                    is_active=True,
                    usage_count=0
                )
                db.session.add(question)

            db.session.commit()
            logger.info(f"Created starter question bank for user {user_id}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating starter question bank for user {user_id}: {e}")
            return False

    @staticmethod
    def setup_complete_starter_content(user_id):
        """Set up all starter content for a new user"""
        try:
            # Create starter kill checklist
            kill_checklist = StarterContentService.create_starter_kill_checklist(user_id)

            # Create starter research template
            research_template = StarterContentService.create_starter_research_template(user_id)

            # Create starter question bank
            question_bank_success = StarterContentService.create_starter_question_bank(user_id)

            success = kill_checklist is not None and research_template is not None and question_bank_success

            logger.info(f"Starter content setup for user {user_id}: {'success' if success else 'partial/failed'}")

            return {
                'success': success,
                'kill_checklist_id': kill_checklist.id if kill_checklist else None,
                'research_template_id': research_template.id if research_template else None,
                'question_bank_created': question_bank_success
            }

        except Exception as e:
            logger.error(f"Error setting up starter content for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def create_first_research_project(user_id, company_id, template_id, company_name):
        """Create the user's first research project"""
        try:
            research_project = ResearchProject(
                user_id=user_id,
                template_id=template_id,
                company_id=company_id,
                name=f"Research: {company_name}",
                description=f"First research project created during onboarding for {company_name}",
                status='active',
                priority='medium'
            )

            db.session.add(research_project)
            db.session.commit()

            logger.info(f"Created first research project for user {user_id}, company {company_name}")
            return research_project

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating first research project for user {user_id}: {e}")
            return None


# Convenience function for routes
def setup_new_user_content(user_id):
    """Main function to call when setting up a new user"""
    return StarterContentService.setup_complete_starter_content(user_id)