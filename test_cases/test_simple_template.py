#!/usr/bin/env python3
"""
Simple test to verify template can be loaded without URL generation
"""

def test_template_loading():
    """Test that templates can be found by Flask"""
    try:
        from app import create_app
        from jinja2.exceptions import TemplateNotFound

        app = create_app()

        with app.app_context():
            # Test that Flask can find the template
            template = app.jinja_env.get_template('onboarding/welcome.html')
            print("✅ Flask can find onboarding/welcome.html template")
            print(f"   Template name: {template.name}")
            return True

    except TemplateNotFound as e:
        print(f"❌ Template not found: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False

def test_with_request_context():
    """Test template rendering with proper request context"""
    try:
        from app import create_app

        app = create_app()

        with app.test_request_context('/onboarding/start'):
            # Now we have a request context, so url_for should work
            from flask import render_template
            rendered = render_template('onboarding/welcome.html')
            print("✅ Template renders successfully with request context")
            print(f"   Template length: {len(rendered)} characters")

            # Check if template contains expected content
            if "Welcome to Your Investment Journey" in rendered:
                print("✅ Template contains expected content")
                return True
            else:
                print("⚠️  Template rendered but missing expected content")
                return False

    except Exception as e:
        print(f"❌ Error with request context: {e}")
        return False

def main():
    print("🧪 Testing Template Loading")
    print("=" * 40)

    loading_ok = test_template_loading()
    rendering_ok = test_with_request_context()

    success = loading_ok and rendering_ok

    print("\n" + "=" * 40)
    print(f"📊 RESULT: {'✅ TEMPLATES WORKING!' if success else '❌ TEMPLATE ISSUES'}")

    if success:
        print("\n🎉 Template fix successful!")
        print("✅ Flask can find onboarding templates")
        print("✅ Templates render with proper request context")
        print("\n🚀 Ready to test in browser:")
        print("   flask run")
        print("   http://127.0.0.1:5000/onboarding/start")

    return success

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)