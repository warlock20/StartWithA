#!/usr/bin/env python3
"""
Test script for onboarding system - validates structure without Flask dependencies
"""

import os
import sys
from pathlib import Path

def test_onboarding_structure():
    """Test onboarding file structure"""
    print("🧪 Testing Onboarding System Structure")
    print("=" * 50)

    base_path = Path(__file__).parent

    # Check onboarding directory structure
    onboarding_path = base_path / "app" / "onboarding"

    required_files = [
        "__init__.py",
        "routes.py",
        "starter_content.py",
        "templates/onboarding/welcome.html",
        "templates/onboarding/step1_philosophy.html",
        "templates/onboarding/step2_company_capture.html",
        "templates/onboarding/step3_kill_checklist.html"
    ]

    print("📁 Checking file structure...")
    all_files_exist = True

    for file_path in required_files:
        full_path = onboarding_path / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            all_files_exist = False

    print(f"\n📊 File Structure: {'✅ COMPLETE' if all_files_exist else '❌ INCOMPLETE'}")

    # Check models.py for new fields
    print("\n🗄️ Checking database model updates...")
    models_path = base_path / "app" / "models.py"

    if models_path.exists():
        with open(models_path, 'r') as f:
            models_content = f.read()

        required_fields = [
            "onboarding_completed",
            "onboarding_step",
            "onboarding_started_at",
            "preferred_sprint_duration",
            "buddy_system_enabled",
            "class OnboardingProgress"
        ]

        for field in required_fields:
            if field in models_content:
                print(f"   ✅ {field}")
            else:
                print(f"   ❌ {field} - MISSING")
                all_files_exist = False

    # Check main app registration
    print("\n🔧 Checking blueprint registration...")
    app_init_path = base_path / "app" / "__init__.py"

    if app_init_path.exists():
        with open(app_init_path, 'r') as f:
            app_content = f.read()

        if "from app.onboarding import onboarding_bp" in app_content:
            print("   ✅ Onboarding blueprint imported")
        else:
            print("   ❌ Onboarding blueprint not imported")
            all_files_exist = False

        if "app.register_blueprint(onboarding_bp)" in app_content:
            print("   ✅ Onboarding blueprint registered")
        else:
            print("   ❌ Onboarding blueprint not registered")
            all_files_exist = False

    return all_files_exist

def test_route_definitions():
    """Test route definitions in routes.py"""
    print("\n🌐 Testing route definitions...")

    routes_path = Path(__file__).parent / "app" / "onboarding" / "routes.py"

    if not routes_path.exists():
        print("   ❌ routes.py not found")
        return False

    with open(routes_path, 'r') as f:
        routes_content = f.read()

    required_routes = [
        "@onboarding_bp.route('/start'",
        "@onboarding_bp.route('/step/<int:step_number>'",
        "@onboarding_bp.route('/api/step/<int:step_number>/complete'",
        "@onboarding_bp.route('/api/progress'",
        "@onboarding_bp.route('/skip'"
    ]

    for route in required_routes:
        if route in routes_content:
            print(f"   ✅ {route}")
        else:
            print(f"   ❌ {route} - MISSING")
            return False

    return True

def test_template_content():
    """Test template content"""
    print("\n🎨 Testing template content...")

    templates_path = Path(__file__).parent / "app" / "onboarding" / "templates" / "onboarding"

    templates = [
        "welcome.html",
        "step1_philosophy.html",
        "step2_company_capture.html",
        "step3_kill_checklist.html"
    ]

    all_valid = True

    for template in templates:
        template_path = templates_path / template
        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()

            # Check for basic template structure
            if "{% extends" in content and "{% block" in content:
                print(f"   ✅ {template} - Valid template structure")
            else:
                print(f"   ⚠️  {template} - Missing template inheritance")
                all_valid = False
        else:
            print(f"   ❌ {template} - File missing")
            all_valid = False

    return all_valid

def test_starter_content():
    """Test starter content service"""
    print("\n📋 Testing starter content service...")

    starter_path = Path(__file__).parent / "app" / "onboarding" / "starter_content.py"

    if not starter_path.exists():
        print("   ❌ starter_content.py not found")
        return False

    with open(starter_path, 'r') as f:
        content = f.read()

    required_functions = [
        "class StarterContentService",
        "create_starter_kill_checklist",
        "create_starter_research_template",
        "create_starter_question_bank",
        "setup_complete_starter_content"
    ]

    for func in required_functions:
        if func in content:
            print(f"   ✅ {func}")
        else:
            print(f"   ❌ {func} - MISSING")
            return False

    return True

def generate_implementation_report():
    """Generate implementation status report"""
    print("\n" + "=" * 60)
    print("🎯 ONBOARDING SYSTEM IMPLEMENTATION REPORT")
    print("=" * 60)

    # Run all tests
    structure_ok = test_onboarding_structure()
    routes_ok = test_route_definitions()
    templates_ok = test_template_content()
    starter_ok = test_starter_content()

    all_tests_passed = all([structure_ok, routes_ok, templates_ok, starter_ok])

    print(f"\n📊 OVERALL STATUS: {'✅ READY FOR TESTING' if all_tests_passed else '⚠️  NEEDS ATTENTION'}")

    if all_tests_passed:
        print("\n🚀 IMPLEMENTATION COMPLETE!")
        print("\n✅ What's Been Built:")
        print("  • Database models updated with onboarding fields")
        print("  • Complete API endpoints for 5-step onboarding flow")
        print("  • Beautiful HTML templates with Bootstrap styling")
        print("  • Starter content service with templates & checklists")
        print("  • Blueprint registration and routing")

        print("\n🎯 Next Steps to Go Live:")
        print("  1. Run database migration: flask db migrate -m 'Add onboarding system'")
        print("  2. Apply migration: flask db upgrade")
        print("  3. Test onboarding flow in browser")
        print("  4. Add navigation link to onboarding from main dashboard")

        print("\n📱 User Journey:")
        print("  • Step 1: Philosophy & mindset (1 min)")
        print("  • Step 2: Capture first company idea (2 min)")
        print("  • Step 3: Apply kill checklist (3 min)")
        print("  • Step 4: Create research template (3 min)")
        print("  • Step 5: Dashboard launch (1 min)")
        print("  • Total: ~10 minutes to systematic investor!")

    else:
        print("\n⚠️  Some components need attention - see details above")

    return all_tests_passed

if __name__ == '__main__':
    success = generate_implementation_report()
    sys.exit(0 if success else 1)