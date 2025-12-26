# In app/tasks.py
import os
import shutil
import uuid
import re
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import yfinance as yf
import pandas as pd

from secedgar import filings, FilingType
from flask import current_app

from app import db, create_app
from app.models import Company, CompanyDocument, User, CompanyArticle, ScuttlebuttAnalysis, FinancialData, BackgroundTask, WorkSession
from celery_app import celery
from dateutil.parser import isoparse

from app.services.ai import generate_ai_content
from app.services.ai.prompt_service import get_competitor_analysis_prompt
from app.utils.time_utils import now_utc

@celery.task(bind=True)
def fetch_financial_data_task(self, company_id):
    """
    A Celery task to fetch historical financial data for a company.
    """
    app = create_app()
    with app.app_context():
        company = Company.query.get(company_id)
        if not company or not company.creator: # Check for company and its user
            return f"Task failed: Company {company_id} or its creator not found."

        # 1. Determine data depth based on user's subscription tier
        user = company.creator
        years_to_fetch = 5 if user.subscription_tier == 'free' else 15

        print(f"BACKGROUND TASK ({self.request.id}): Fetching {years_to_fetch} years of financial data for {company.ticker_symbol}...")

        try:
            ticker = yf.Ticker(company.ticker_symbol)

            # Define which metrics we want to extract
            # Key must match the index of the yfinance DataFrame
            metrics_to_get = {
                'income_statement': ['Total Revenue', 'Net Income'],
                'balance_sheet': ['Total Assets', 'Total Liab', 'Stockholders Equity'],
                'cash_flow': ['Free Cash Flow']
            }

            # A map to the yfinance functions
            statement_map = {
                'income_statement': ticker.income_stmt,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow
            }

            saved_count = 0
            for statement_type, metrics in metrics_to_get.items():
                # Get the financial statement DataFrame from yfinance
                statement_df = statement_map[statement_type]
                if statement_df.empty:
                    continue

                # Limit to the number of years for the tier
                statement_df = statement_df.iloc[:, :years_to_fetch]

                for metric_name in metrics:
                    if metric_name in statement_df.index:
                        # Iterate through each column (each column is a period/year)
                        for period_date, value in statement_df.loc[metric_name].items():
                            # Check if this data point already exists
                            existing_data = FinancialData.query.filter_by(
                                company_id=company.id,
                                metric_name=metric_name,
                                period_date=period_date.date()
                            ).first()

                            if existing_data:
                                continue # Skip duplicates

                            new_data_point = FinancialData(
                                company_id=company.id,
                                statement_type=statement_type,
                                metric_name=metric_name,
                                period_date=period_date.date(),
                                value=int(value) if pd.notna(value) else 0
                            )
                            db.session.add(new_data_point)
                            saved_count += 1

            if saved_count > 0:
                db.session.commit()

            result_message = f"Successfully saved {saved_count} new financial data points for {company.name}."
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            db.session.rollback()
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")
            return f"Task failed: {e}"


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
                print(f"BACKGROUND TASK FAILED ({self.request.id}): Task {task_id} not found")
                return f"Task {task_id} not found"

            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            print(f"BACKGROUND TASK ({self.request.id}): Starting competitor analysis for {company_data['name']}...")

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
            print(f"BACKGROUND TASK ({self.request.id}): Calling LLM service...")
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
            import json
            task.result = json.dumps({
                "analysis": competitor_analysis,
                "message": "Competitor analysis completed successfully!"
            })

            db.session.commit()

            result_message = f"Competitor analysis completed successfully for {company_data['name']}"
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")

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

        print(f"BACKGROUND TASK ({self.request.id}): Fetching news for {company.name}...")

        try:
            # Construct the API request URL. We'll search for the company name.
            # Adding "-stock" or "-shares" can sometimes filter out purely financial market noise.
            # sortBy=relevancy is a good default.
            url = (f"https://newsapi.org/v2/everything?"
                   f"q={company.name}&"
                   f"sortBy=relevancy&"
                   f"language=en&"
                   f"apiKey={api_key}")

            response = requests.get(url)
            response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)

            data = response.json()
            articles_from_api = data.get('articles', [])

            new_articles_count = 0
            for article_data in articles_from_api:
                article_url = article_data.get('url')
                if not article_url:
                    continue

                # Check if we've already saved this article to avoid duplicates
                existing_article = CompanyArticle.query.filter_by(url=article_url).first()
                if existing_article:
                    continue # Skip to the next article

                # Parse the publication date string into a datetime object
                published_at_str = article_data.get('publishedAt')
                published_at_dt = None
                if published_at_str:
                    try:
                        published_at_dt = isoparse(published_at_str)
                    except ValueError:
                        print(f"Could not parse date: {published_at_str}")
                        continue # Skip if date is invalid

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

            result_message = f"Successfully fetched and saved {new_articles_count} new articles for {company.name}."
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            db.session.rollback()
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")
            return f"Task failed: {e}"


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
                print(f"BACKGROUND TASK FAILED ({self.request.id}): Task {task_id} not found")
                return f"Task {task_id} not found"

            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            print(f"BACKGROUND TASK ({self.request.id}): Starting competitor analysis for {company_data['name']}...")

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
            print(f"BACKGROUND TASK ({self.request.id}): Calling LLM service...")
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

            result_message = f"Competitor analysis completed successfully for {company_data['name']}"
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return f"Task failed: {e}"

@celery.task(bind=True)
def fetch_sec_filings_task(self, company_id, user_id, years_to_fetch=5):
    """
    A Celery task to fetch SEC filings in the background.
    We create a minimal app context ONLY within the task.
    """
    # Create an app instance and push a context FOR THIS TASK ONLY
    app = create_app()
    with app.app_context():
        # All your previous task logic can go here.
        # It now has access to the database and app.config via current_app.
        company = Company.query.get(company_id)
        user = User.query.get(user_id)
        if not company or not user:
            #print(f"Task failed: Company {company_id} or User {user_id} not found.")
            return "Task failed: Company or User not found."

        # Use 'current_app' to access config, which is available thanks to the app context.
        temp_download_path = Path(current_app.instance_path) / f"sec_temp_{self.request.id}"
        user_agent = f"{user.username} {user.email}"
        filing_type_str = '10-K'
        filing_type_enum = FilingType.FILING_10K

        try:
            #print(f"BACKGROUND TASK ({self.request.id}): Fetching filings for {company.ticker_symbol}...")
            start_date = (now_utc() - timedelta(days=years_to_fetch * 365.25)).date()
            
            filing_docs = filings(
                cik_lookup=company.ticker_symbol,
                filing_type=filing_type_enum,
                start_date=start_date,
                user_agent=user_agent
            )
            filing_docs.save(temp_download_path)

            # The rest of the file processing logic is the same as it was in your route
            # It opens the downloaded files, parses them, and saves them to the DB.
            # ... (Paste the entire file processing loop from your old route here) ...

            company_filing_path = temp_download_path / company.ticker_symbol.upper() / filing_type_str
            saved_count = 0

            if company_filing_path.exists():
                # This loop finds each downloaded file.
                for submission_file_path in company_filing_path.glob('*.txt'):
                    if not submission_file_path.is_file():
                        continue

                    print(f"Processing downloaded file: {submission_file_path.name}")
                        
                    with open(submission_file_path, 'r', encoding='utf-8') as f:
                        full_filing_text = f.read()

                    # STEP 1: Parse the Filing Date
                    filing_date_str = "N/A"
                    for line in full_filing_text.splitlines()[:40]:
                        if "FILED AS OF DATE:" in line:
                            date_val = line.split(":")[-1].strip()
                            filing_date_str = f"{date_val[0:4]}-{date_val[4:6]}-{date_val[6:8]}"
                            break
                        
                    # STEP 2: Check for Duplicates
                    doc_title = f"{filing_type_str} Report ({filing_date_str})"
                    existing_doc = CompanyDocument.query.filter_by(company_id=company.id, document_title=doc_title).first()
                    if existing_doc:
                        print(f"Skipping already existing filing: {doc_title}")
                        continue

                    # STEP 3: Parse the Clean HTML Content
                    doc_start_pattern = re.compile(r'<DOCUMENT>')
                    doc_end_pattern = re.compile(r'</DOCUMENT>')
                    doc_type_pattern = re.compile(r'<TYPE>' + re.escape(filing_type_str))
                    docs = list(zip([m.end() for m in doc_start_pattern.finditer(full_filing_text)], [m.start() for m in doc_end_pattern.finditer(full_filing_text)]))
                        
                    html_content = ''
                    for doc_start, doc_end in docs:
                        doc_text = full_filing_text[doc_start:doc_end]
                        if doc_type_pattern.search(doc_text):
                            text_start = re.search(r'<TEXT>', doc_text)
                            text_end = re.search(r'</TEXT>', doc_text)
                            if text_start and text_end:
                                html_content = doc_text[text_start.end():text_end.start()]
                                html_tag_start = html_content.find('<HTML>')
                                if html_tag_start != -1:
                                    html_content = html_content[html_tag_start:]
                                break 
                        
                    if not html_content:
                        print(f"WARNING: Could not extract clean HTML from {submission_file_path.name}")
                        continue

                    # STEP 4: Save the Clean HTML and Create DB Record
                    original_fn = f"{company.ticker_symbol}_{filing_type_str}_{filing_date_str}.html"
                    stored_fn_uuid = f"{uuid.uuid4().hex}.html"
                    company_permanent_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(company.id))
                    os.makedirs(company_permanent_path, exist_ok=True)
                    file_save_path = os.path.join(company_permanent_path, stored_fn_uuid)

                    with open(file_save_path, 'w', encoding='utf-8') as f_out:
                        f_out.write(html_content)

                    new_doc = CompanyDocument(
                        company_id=company.id, user_id=user.id,
                        original_filename=original_fn,
                        stored_filename=os.path.join(str(company.id), stored_fn_uuid),
                        document_group=f"SEC {filing_type_str} Filings",
                        document_title=doc_title,
                        document_date=datetime.strptime(filing_date_str, '%Y-%m-%d').date() if filing_date_str != "N/A" else None
                    )
                    db.session.add(new_doc)
                    saved_count += 1
                                    
                    # After the loop is finished, check if anything was saved
            if saved_count > 0:
                db.session.commit()

            result_message = f"Successfully processed {saved_count} new filings for {company.ticker_symbol}."
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            db.session.rollback()
            print(f"BACKGROUND TASK FAILED ({self.request.id}) for {company.ticker_symbol}: {e}")
            # You can use self.update_state to store error info if needed
            # self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
            return f"Task failed for {company.ticker_symbol}: {e}"
        
        finally:
            if temp_download_path.exists():
                shutil.rmtree(temp_download_path)
                
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

        articles = company.articles.order_by(CompanyArticle.published_at.desc()).limit(20).all() # Get up to 20 recent articles
        if not articles:
            return "Analysis failed: No articles found for this company to analyze."

        # Concatenate article content to create the context for the LLM
        context_for_llm = ""
        for article in articles:
            context_for_llm += f"Title: {article.title}\n"
            if article.description:
                context_for_llm += f"Description: {article.description}\n"
            context_for_llm += "---\n"

        # Configure Gemini API (ensure API key is in config)
        gemini_api_key = current_app.config.get('GEMINI_API_KEY')
        if not gemini_api_key:
            return "Task failed: Gemini API key is not configured."

        try:
            # A powerful prompt to guide the AI
            prompt = (
                "You are a financial analyst stress-testing an investment thesis. Based *only* on the context from the following news article titles and descriptions, "
                "provide a concise summary of recent developments. Then, explicitly identify two potential bull cases (opportunities or positive sentiment) and two "
                "potential bear cases (risks or negative sentiment). Format your response clearly with 'Summary', 'Bull Cases', and 'Bear Cases' headings.\n\n"
                f"CONTEXT:\n---\n{context_for_llm[:28000]}\n---\n\n" # Truncate context to be safe
                "ANALYSIS:"
            )

            print(f"BACKGROUND TASK ({self.request.id}): Sending Scuttlebutt prompt to unified LLM service for {company.name}...")
            ai_summary = generate_ai_content(prompt)

            # Save the new analysis to the database
            new_analysis = ScuttlebuttAnalysis(
                company_id=company.id,
                generated_summary=ai_summary
            )
            db.session.add(new_analysis)
            db.session.commit()

            result_message = f"AI Scuttlebutt analysis for {company.name} completed successfully."
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            db.session.rollback()
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")
            return f"Task failed: {e}"


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
                print(f"BACKGROUND TASK FAILED ({self.request.id}): Task {task_id} not found")
                return f"Task {task_id} not found"

            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            print(f"BACKGROUND TASK ({self.request.id}): Starting competitor analysis for {company_data['name']}...")

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
            print(f"BACKGROUND TASK ({self.request.id}): Calling LLM service...")
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
            import json
            task.result = json.dumps({
                "analysis": competitor_analysis,
                "message": "Competitor analysis completed successfully!"
            })

            db.session.commit()

            result_message = f"Competitor analysis completed successfully for {company_data['name']}"
            print(f"BACKGROUND TASK ({self.request.id}): Finished. {result_message}")
            return result_message

        except Exception as e:
            print(f"BACKGROUND TASK FAILED ({self.request.id}): {e}")

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return f"Task failed: {e}"