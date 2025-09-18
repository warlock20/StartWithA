# company_research_platform/config.py

import os
from dotenv import load_dotenv # Import the library

# Define the base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file
# This line will look for a .env file in the current directory (where config.py is)
# or in parent directories, and load the variables found into the environment.
load_dotenv(os.path.join(basedir, '.env')) # Load .env file for PostgreSQL configuration

class Config:
    """Base configuration."""
    # Now, os.environ.get() will be able to find variables set in your .env file
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-default'
    
    # Example: if DATABASE_URL is in your .env, it will be used
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db') # Default if not in .env
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
    print(f"Using Gemini API Key: {GEMINI_API_KEY}")
    print(f"Using News API Key: {NEWS_API_KEY}")
    # You can also load Flask specific config directly if set in .env
    # For example, FLASK_DEBUG=1 or FLASK_ENV=development
    # Though these are often handled by how you run the Flask CLI or app.run()
    
    UPLOAD_FOLDER = os.path.join(basedir, 'instance', 'uploads', 'company_documents')
    ALLOWED_EXTENSIONS = {'pdf', 'txt'} # Allow PDFs and text files for now
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Limit upload size to 16 MB
    
    CACHE_TYPE = "SimpleCache"  # Use a simple in-memory cache
    CACHE_DEFAULT_TIMEOUT = 300 # Default timeout in seconds (e.g., 5 minutes)
    
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    
    # Set the default subscription tier for newly registered users.
    # Use 'premium' for development/testing, change to 'free' for production.
    DEFAULT_USER_TIER = 'premium'