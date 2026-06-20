# Investment Checklist Platform
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

# Load .env only in local development. 
# Railway injects variables directly into the environment.
if os.path.exists(os.path.join(basedir, '.env')):
    load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Production configuration."""
    
    # 1. SECURITY: Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-in-railway-dashboard'

    # 2. DATABASE: Handle Railway Postgres URL Fix
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url and _db_url.startswith("postgres://"):
        # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'pool_pre_ping': True,
    }


    # 3. COOKIES & GDPR: Security settings for German/EU residency
    # Ensure this is TRUE in Railway to prevent session hijacking over non-HTTPS
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # 4. API KEYS (No print statements in production logs!)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
    
    # 5. STORAGE: Persistent Volume Path
    # Note: On Railway, local files are deleted on restart. 
    # Use /app/instance/uploads and mount a Railway Volume there.
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, 'instance', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'txt'}
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
    
    # 6. CACHE: Use Redis for caching if available, otherwise fallback
    # Since you are using Redis for Celery, it's better to use it for cache too.
    CACHE_TYPE = "RedisCache" if os.environ.get('REDIS_URL') else "SimpleCache"
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    CACHE_DEFAULT_TIMEOUT = 300 
    
    # 7. CELERY: Use Railway's Redis Service
    # Use REDIS_URL from environment; defaults to local for dev
    CELERY_BROKER_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # 8. BUSINESS LOGIC
    DEFAULT_USER_TIER = os.environ.get('DEFAULT_USER_TIER', 'free')

    # 8b. BRAND: Single source of truth for the product name/tagline.
    # Defined once here so the name can be changed in one place.
    APP_NAME = os.environ.get('APP_NAME', 'Start with A')
    APP_TAGLINE = os.environ.get('APP_TAGLINE', 'Research every company. Miss nothing.')

    # 9. AUTH0 CONFIGURATION
    AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
    AUTH0_CLIENT_ID = os.environ.get('AUTH0_CLIENT_ID')
    AUTH0_CLIENT_SECRET = os.environ.get('AUTH0_CLIENT_SECRET')

    # Auto-detect callback URL from Railway's PUBLIC_URL or explicit AUTH0_CALLBACK_URL
    # Railway provides RAILWAY_PUBLIC_DOMAIN and RAILWAY_STATIC_URL
    _public_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN') or os.environ.get('RAILWAY_STATIC_URL')
    if _public_domain:
        # Railway detected — use HTTPS callback
        _callback_base = f'https://{_public_domain}' if not _public_domain.startswith('http') else _public_domain
        AUTH0_CALLBACK_URL = os.environ.get('AUTH0_CALLBACK_URL') or f'{_callback_base}/auth/callback'
    else:
        # Local development
        AUTH0_CALLBACK_URL = os.environ.get('AUTH0_CALLBACK_URL') or 'http://localhost:5000/auth/callback'

    AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE')

    # 10. RATE LIMITING: Protection against brute force and abuse
    # Uses Redis if available, otherwise in-memory storage
    # Specific rate limits are defined in app/constants.py
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL') or 'memory://'
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_DEFAULT = '200 per minute'
    RATELIMIT_HEADERS_ENABLED = True