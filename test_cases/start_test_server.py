#!/usr/bin/env python3
"""
Start development server for onboarding testing
"""

import os
import sys
import subprocess

def create_test_user():
    """Create a test user for onboarding testing"""
    try:
        from app import create_app, db
        from app.models import User

        app = create_app()
        with app.app_context():
            # Check if test user already exists
            existing_user = User.query.filter_by(email='onboarding-test@example.com').first()
            if existing_user:
                print("✅ Test user already exists: onboarding-test@example.com")
                return True

            # Create new test user
            user = User(
                username='onboarding-test',
                email='onboarding-test@example.com'
            )
            user.set_password('test123')
            db.session.add(user)
            db.session.commit()

            print("✅ Test user created successfully!")
            print("   Username: onboarding-test")
            print("   Email: onboarding-test@example.com")
            print("   Password: test123")
            return True

    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return False

def check_environment():
    """Check if environment is ready for testing"""
    print("🔍 Checking Environment...")

    # Check if virtual environment is activated
    if 'VIRTUAL_ENV' not in os.environ:
        print("⚠️  Virtual environment not detected")
        print("   Run: source venv/bin/activate")
        return False

    # Check if Flask is available
    try:
        import flask
        print(f"✅ Flask available: {flask.__version__}")
    except ImportError:
        print("❌ Flask not available")
        return False

    # Check if app can be imported
    try:
        from app import create_app
        app = create_app()
        print("✅ App can be created successfully")
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        return False

    return True

def start_development_server():
    """Start the Flask development server"""
    print("\n🚀 Starting Development Server...")
    print("=" * 50)

    # Set environment variables
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'

    print("📍 Server will be available at: http://127.0.0.1:5000")
    print("🎯 Onboarding start URL: http://127.0.0.1:5000/onboarding/start")
    print("\n🧪 Testing Instructions:")
    print("1. Open browser and go to http://127.0.0.1:5000")
    print("2. Login with: onboarding-test@example.com / test123")
    print("3. Navigate to: http://127.0.0.1:5000/onboarding/start")
    print("4. Experience the complete 10-minute onboarding journey!")
    print("\n⏹️  Press Ctrl+C to stop the server when done")
    print("=" * 50)

    try:
        # Start Flask development server
        subprocess.run(['flask', 'run', '--host=127.0.0.1', '--port=5000'], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Happy testing!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting server: {e}")
        return False

    return True

def main():
    """Main testing setup function"""
    print("🧪 Setting Up Onboarding Flow Testing")
    print("=" * 50)

    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix issues above.")
        return False

    # Create test user
    if not create_test_user():
        print("\n❌ Test user creation failed.")
        return False

    print("\n✅ Environment ready for testing!")

    # Ask user if they want to start server
    response = input("\n🚀 Start development server now? (y/n): ").lower().strip()

    if response in ['y', 'yes']:
        return start_development_server()
    else:
        print("\n📋 Manual Testing Instructions:")
        print("1. Run: flask run")
        print("2. Open: http://127.0.0.1:5000/onboarding/start")
        print("3. Login: onboarding-test@example.com / test123")
        print("4. Experience the onboarding flow!")
        return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)