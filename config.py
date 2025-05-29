# company_research_platform/config.py

import os
from dotenv import load_dotenv # Import the library

# Define the base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file
# This line will look for a .env file in the current directory (where config.py is)
# or in parent directories, and load the variables found into the environment.
load_dotenv(os.path.join(basedir, '.env')) # Explicitly point to .env in project root

class Config:
    """Base configuration."""
    # Now, os.environ.get() will be able to find variables set in your .env file
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-default'
    
    # Example: if DATABASE_URL is in your .env, it will be used
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db') # Default if not in .env
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # You can also load Flask specific config directly if set in .env
    # For example, FLASK_DEBUG=1 or FLASK_ENV=development
    # Though these are often handled by how you run the Flask CLI or app.run()
    
    UPLOAD_FOLDER = os.path.join(basedir, 'instance', 'uploads', 'company_documents')
    ALLOWED_EXTENSIONS = {'pdf', 'txt'} # Allow PDFs and text files for now
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Limit upload size to 16 MB