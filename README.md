## Vision: An Intelligent Investment Platform for the Modern Researcher

### The Problem

Today's investors are overwhelmed by information but lack actionable wisdom. Information overload, emotional biases, and inconsistent research processes often lead to poor decisions and repeated mistakes.

### Our Solution

We are building an intelligent investment platform to help serious investors develop, refine, and execute a unique, systematic research process. Inspired by the wisdom of legendary investors like Charlie Munger, our platform is not a stock screener—it is a framework to help you improve how you think.

At its core, the platform empowers you to build a personalized, AI-assisted workflow that enforces discipline and accelerates your research.

---

### Key Pillars of the Platform

#### 1. Capture, Filter, and Focus with the "Idea Pipeline"

- **Quick Capture:** Instantly log any investment idea—from a stock tip to a market trend—before it slips away.
- **The "Kill Checklist":** Inspired by the principle of inversion, this feature helps you quickly and ruthlessly eliminate bad ideas based on your own deal-breaker criteria, saving your most valuable asset: time.

#### 2. Conduct Systematic, In-Depth Analysis with "Research Templates"

- **Custom Workflows:** Design reusable research workflows that reflect your unique investment style—whether value, growth, or special situations.
- **Structured Process:** Move beyond random note-taking and follow a step-by-step process to ensure you never miss a critical piece of due diligence.

#### 3. Leverage Your Personal AI Research Assistant

- **AI-Powered Insights:** Integrate powerful AI and Large Language Models (LLMs) to supercharge your research.
- **Instant Analysis:** Analyze financial documents, earnings call transcripts, and news to extract key insights, identify risks, and get answers to your most pressing questions in seconds.

#### 4. Create a Continuous Learning Loop

- **Research Journal:** Log your thoughts, connect ideas, and track the evolution of your investment thesis over time.
- **Mistake Log:** Systematically document errors, understand root causes, and turn mistakes into lessons integrated back into your checklists.
- **Analytics Dashboard:** Gain insights into your research habits, decision patterns, and most successful idea sources to improve your own behavior.

## Research Workflow

The platform supports two parallel research workflows that can intersect:

### Company Workflow

```
Add Company → Idea Inbox → Kill Process → [Survives] → Research
```

1. **Add Company**: Add a company to the system
2. **Idea Inbox**: Company enters the idea inbox for initial evaluation
3. **Kill Process**: Company undergoes kill process to validate investment thesis
4. **Research**: If company survives kill process, full research project is initiated

### Sector Workflow

```
Add Sector Idea → [Inbox or Research] → Sector Research → Discover Companies → [Optional: Add to Inbox]
                                                                                          ↓
                                                                                   Company Workflow
```

1. **Add Sector Idea**: Identify a sector of interest
2. **Inbox or Research**: Keep idea in inbox or proceed to sector research
3. **Sector Research**: Conduct research on the sector
4. **Discover Companies**: Identify relevant companies during research
5. **Optional Company Addition**: Add discovered companies to idea inbox, initiating the Company Workflow

**Workflow Intersection**: Sector research feeds into company research through the idea inbox. Companies discovered during sector research can be added to the inbox and then follow the standard Company Workflow.

## Features

- Create and manage investment checklists (with hierarchical items)
- Add, edit, and remove checklist items (supports sub-items)
- Manage companies and sectors to research
- Idea pipeline with inbox and kill process
- Start research sessions for companies using checklists
- Sector research with company discovery
- Save answers for each checklist item per research session
- Resume in-progress research or review completed sessions
- All data stored in a relational database (SQLite by default)
- Background task processing with Celery (e.g., for long-running jobs or notifications)

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/investment-checklist.git
cd investment-checklist
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy `.env.example` to `.env` and edit as needed, or use the provided `.env` file.

### 5. Initialize the database

```bash
flask --app run.py init-db
```

### 6. Run the application

```bash
flask --app run.py run
```

Or, for development with auto-reload:

```bash
export FLASK_APP=run.py
export FLASK_DEBUG=1
flask run
```

The app will be available at [http://localhost:5000](http://localhost:5000).

### 7. Start Celery Worker

Celery requires a message broker (e.g., Redis). Make sure your broker is running, then start the worker:

```bash
celery -A app.celery worker --loglevel=info
```

## Usage

- Create checklists and companies via the web interface.
- Start a research session for a company using a checklist.
- Answer checklist items and track your research progress.
- Resume unfinished sessions or review completed ones.
- Background tasks (such as notifications or data processing) are handled by Celery.

## Project Structure

- `app/` - Flask application code (models, routes, templates, Celery tasks)
- `run.py` - Application entry point and CLI commands
- `config.py` - Configuration (uses `.env`)
- `.env` - Environment variables (secret keys, DB URL, broker URL, etc.)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.