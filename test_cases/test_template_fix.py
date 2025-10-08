#!/usr/bin/env python3
"""
Test if onboarding templates can be found and rendered
"""

def test_template_rendering():
    """Test that onboarding templates can be rendered"""
    try:
        from app import create_app
        from flask import render_template

        app = create_app()

        with app.app_context():
            # Test that we can render the welcome template
            try:
                rendered = render_template('onboarding/welcome.html')
                print("✅ welcome.html template renders successfully")
                print(f"   Template length: {len(rendered)} characters")
                return True
            except Exception as e:
                print(f"❌ Error rendering welcome.html: {e}")
                return False

    except Exception as e:
        print(f"❌ Error setting up app: {e}")
        return False

def test_route_access():
    """Test that onboarding routes are accessible"""
    try:
        from app import create_app

        app = create_app()

        with app.test_client() as client:
            # Test GET request to onboarding start (should redirect to login)
            response = client.get('/onboarding/start')
            print(f"✅ /onboarding/start responds with status: {response.status_code}")

            # 302 is expected (redirect to login) for non-authenticated user
            if response.status_code in [200, 302]:
                print("✅ Route is accessible (redirect to login is expected)")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Error testing routes: {e}")
        return False

def main():
    """Run template fix tests"""
    print("🧪 Testing Template Fix")
    print("=" * 40)

    template_ok = test_template_rendering()
    route_ok = test_route_access()

    success = template_ok and route_ok

    print("\n" + "=" * 40)
    print(f"📊 RESULT: {'✅ TEMPLATES FIXED!' if success else '❌ STILL ISSUES'}")

    if success:
        print("\n🎉 Onboarding templates are working!")
        print("🚀 You can now test the onboarding flow:")
        print("   1. Run: flask run")
        print("   2. Open: http://127.0.0.1:5000/onboarding/start")
        print("   3. Login and experience the journey!")

    return success

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)