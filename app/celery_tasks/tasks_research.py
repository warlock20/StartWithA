"""
Research & Company Analysis Celery Tasks

Background tasks for competitor analysis, scuttlebutt analysis, and news fetching.
"""

import json
import logging
import requests
from flask import current_app
from dateutil.parser import isoparse

from app import db, create_app
from app.models import Company, CompanyArticle, ScuttlebuttAnalysis, BackgroundTask, WorkSession
from celery_app import celery

from app.services.ai import generate_ai_content
from app.services.ai.prompt_service import get_competitor_analysis_prompt
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def competitor_analysis_task(self, task_id, company_data):
    """
    A Celery task to perform AI competitor analysis for a company.
    """
    app = create_app()
    with app.app_context():
        try:
            # Get fresh task instance from database
            task = BackgroundTask.query.get(task_id)
            if not task:
                logger.error(f"TASK {self.request.id}: Task {task_id} not found")
                return f"Task {task_id} not found"

            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Starting competitor analysis for {company_data['name']}")

            # Generate the analysis prompt
            analysis_prompt = get_competitor_analysis_prompt(
                'landscape_analysis',
                company_name=company_data['name'],
                ticker_symbol=company_data['ticker_symbol'],
                company_description=company_data['summary'] or 'No description available',
                sector=company_data['sector'] or 'Unknown',
                industry=company_data['industry'] or 'Unknown'
            )

            # Call LLM service - this is where the long wait happens
            logger.info(f"TASK {self.request.id}: Calling LLM service...")
            competitor_analysis = generate_ai_content(analysis_prompt, max_tokens=2000)

            # Store result in work session
            session = WorkSession.query.filter_by(
                research_project_id=task.project_id,
                user_id=task.user_id,
                step_index=task.step_index,
                end_time=None
            ).first()

            if session:
                session.notes = competitor_analysis
                session.updated_at = now_utc()

            # Update task as completed
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                "analysis": competitor_analysis,
                "message": "Competitor analysis completed successfully!"
            })

            db.session.commit()

            logger.info(f"TASK {self.request.id}: Completed successfully")
            return f"Competitor analysis completed successfully for {company_data['name']}"

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Failed - {e}", exc_info=True)

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return f"Task failed: {e}"


@celery.task(bind=True)
def fetch_company_news_task(self, company_id):
    """
    A Celery task to fetch recent news for a company from NewsAPI.org.
    """
    app = create_app()
    with app.app_context():
        company = Company.query.get(company_id)
        if not company:
            return f"Task failed: Company {company_id} not found."

        api_key = current_app.config.get('NEWS_API_KEY')
        if not api_key:
            return "Task failed: News API key is not configured."

        logger.info(f"TASK {self.request.id}: Fetching news for {company.name}")

        try:
            url = (f"https://newsapi.org/v2/everything?"
                   f"q={company.name}&"
                   f"sortBy=relevancy&"
                   f"language=en&"
                   f"apiKey={api_key}")

            response = requests.get(url)
            response.raise_for_status()

            data = response.json()
            articles_from_api = data.get('articles', [])

            new_articles_count = 0
            for article_data in articles_from_api:
                article_url = article_data.get('url')
                if not article_url:
                    continue

                # Check for duplicates
                existing_article = CompanyArticle.query.filter_by(url=article_url).first()
                if existing_article:
                    continue

                # Parse publication date
                published_at_str = article_data.get('publishedAt')
                published_at_dt = None
                if published_at_str:
                    try:
                        published_at_dt = isoparse(published_at_str)
                    except ValueError:
                        logger.warning(f"Could not parse date: {published_at_str}")
                        continue

                new_article = CompanyArticle(
                    company_id=company.id,
                    title=article_data.get('title', 'No Title'),
                    url=article_url,
                    description=article_data.get('description'),
                    source_name=article_data.get('source', {}).get('name'),
                    published_at=published_at_dt
                )
                db.session.add(new_article)
                new_articles_count += 1

            if new_articles_count > 0:
                db.session.commit()

            logger.info(f"TASK {self.request.id}: Saved {new_articles_count} articles")
            return f"Successfully fetched and saved {new_articles_count} new articles for {company.name}."

        except Exception as e:
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Failed - {e}")
            return f"Task failed: {e}"


@celery.task(bind=True)
def analyze_scuttlebutt_task(self, company_id):
    """
    A Celery task to perform AI analysis on a company's fetched news articles.
    """
    app = create_app()
    with app.app_context():
        company = Company.query.get(company_id)
        if not company:
            return f"Task failed: Company {company_id} not found."

        articles = company.articles.order_by(CompanyArticle.published_at.desc()).limit(20).all()
        if not articles:
            return "Analysis failed: No articles found for this company to analyze."

        # Concatenate article content for LLM
        context_for_llm = ""
        for article in articles:
            context_for_llm += f"Title: {article.title}\n"
            if article.description:
                context_for_llm += f"Description: {article.description}\n"
            context_for_llm += "---\n"

        gemini_api_key = current_app.config.get('GEMINI_API_KEY')
        if not gemini_api_key:
            return "Task failed: Gemini API key is not configured."

        try:
            prompt = (
                "You are a financial analyst stress-testing an investment thesis. Based *only* on the context from the following news article titles and descriptions, "
                "provide a concise summary of recent developments. Then, explicitly identify two potential bull cases (opportunities or positive sentiment) and two "
                "potential bear cases (risks or negative sentiment). Format your response clearly with 'Summary', 'Bull Cases', and 'Bear Cases' headings.\n\n"
                f"CONTEXT:\n---\n{context_for_llm[:28000]}\n---\n\n"
                "ANALYSIS:"
            )

            logger.info(f"TASK {self.request.id}: Analyzing scuttlebutt for {company.name}")
            ai_summary = generate_ai_content(prompt)

            # Save the analysis
            new_analysis = ScuttlebuttAnalysis(
                company_id=company.id,
                generated_summary=ai_summary
            )
            db.session.add(new_analysis)
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Completed successfully")
            return f"AI Scuttlebutt analysis for {company.name} completed successfully."

        except Exception as e:
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Failed - {e}")
            return f"Task failed: {e}"
