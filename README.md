# Investment Checklist Web App

A web application designed to help investors methodically assess investment opportunities through customizable checklists and structured research sessions. It integrates various mental models into a unified workflow for thorough and consistent analysis.

## Features

- Create and manage investment checklists (with hierarchical items)
- Add, edit, and remove checklist items (supports sub-items)
- Manage companies to research
- Start research sessions for a company using a checklist
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