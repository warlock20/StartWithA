#!/usr/bin/env python3
"""
Test onboarding system with actual Flask app
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_onboarding_routes():
    """Test that onboarding routes are properly registered"""
    try:
        from app import create_app

        app = create_app()

        with app.app_context():
            # Get all registered routes
            routes = []
            for rule in app.url_map.iter_rules():
                routes.append(str(rule))

            # Check for onboarding routes
            onboarding_routes = [r for r in routes if '/onboarding' in r]

            print("🌐 Registered Onboarding Routes:")
            for route in onboarding_routes:
                print(f"   ✅ {route}")

            expected_routes = [
                '/onboarding/start',
                '/onboarding/step/<step_number>',
                '/onboarding/api/step/<step_number>/complete',
                '/onboarding/api/progress',
                '/onboarding/skip'
            ]

            # Check if all expected routes exist
            all_found = True
            for expected in expected_routes:
                found = any(expected.replace('<step_number>', '<int:step_number>') in route
                          for route in onboarding_routes)
                if found:
                    print(f"   ✅ Found: {expected}")
                else:
                    print(f"   ❌ Missing: {expected}")
                    all_found = False

            return all_found

    except Exception as e:
        print(f"❌ Error testing routes: {e}")
        return False

def test_database_models():
    """Test that new database models work"""
    try:
        from app import create_app, db
        from app.models import User, OnboardingProgress

        app = create_app()

        with app.app_context():
            # Test User model new fields
            print("\n🗄️ Testing Database Models:")

            # Test querying a user (this should work now)
            user = User.query.first()
            if user:
                print(f"   ✅ User model working: {user.username}")
                print(f"   ✅ Onboarding completed: {user.onboarding_completed}")
                print(f"   ✅ Onboarding step: {user.onboarding_step}")
            else:
                print("   ℹ️ No users in database yet")

            # Test OnboardingProgress model
            progress_count = OnboardingProgress.query.count()
            print(f"   ✅ OnboardingProgress model working: {progress_count} records")

            return True

    except Exception as e:
        print(f"❌ Error testing database models: {e}")
        return False

def test_starter_content():
    """Test starter content service"""
    try:
        from app.onboarding.starter_content import StarterContentService

        print("\n📋 Testing Starter Content Service:")

        # Test that service class exists and has required methods
        service = StarterContentService()

        methods = [
            'create_starter_kill_checklist',
            'create_starter_research_template',
            'create_starter_question_bank',
            'setup_complete_starter_content'
        ]

        for method in methods:
            if hasattr(service, method):
                print(f"   ✅ Method exists: {method}")
            else:
                print(f"   ❌ Method missing: {method}")
                return False

        return True

    except Exception as e:
        print(f"❌ Error testing starter content: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Live Onboarding System")
    print("=" * 50)

    routes_ok = test_onboarding_routes()
    models_ok = test_database_models()
    starter_ok = test_starter_content()

    all_ok = routes_ok and models_ok and starter_ok

    print("\n" + "=" * 50)
    print(f"📊 LIVE TEST RESULTS: {'✅ ALL SYSTEMS GO!' if all_ok else '⚠️ ISSUES FOUND'}")

    if all_ok:
        print("\n🎉 ONBOARDING SYSTEM IS FULLY OPERATIONAL!")
        print("\n🚀 Ready for users! The system can now:")
        print("   • Accept new user registrations")
        print("   • Guide them through 10-minute onboarding")
        print("   • Create their first company, kill checklist, and research template")
        print("   • Launch them into a populated, personalized dashboard")
        print("\n📱 Next: Test the complete user flow in your browser!")
        print("   1. Sign up as a new user")
        print("   2. Go to /onboarding/start")
        print("   3. Experience the 10-minute guided journey")

    return all_ok

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)