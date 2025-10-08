# 🧪 Testing the Complete Onboarding Flow

## 🚀 Method 1: Start Development Server

### Step 1: Start the Flask App
```bash
# In your project directory
source venv/bin/activate
export FLASK_ENV=development
export FLASK_DEBUG=1
flask run
```

### Step 2: Test the Onboarding Journey
1. **Open your browser** and go to: `http://127.0.0.1:5000`
2. **Login** as an existing user OR create a new test user
3. **Start onboarding** by going to: `http://127.0.0.1:5000/onboarding/start`

### Step 3: Experience the 10-Minute Journey
- **Step 1**: Philosophy & mindset (1 min) - See the Munger quote and investment principles
- **Step 2**: Company capture (2 min) - Enter a company you're interested in
- **Step 3**: Kill checklist (3 min) - Experience systematic filtering with 3 questions
- **Step 4**: Research template (3 min) - See your personalized research roadmap created
- **Step 5**: Dashboard launch (1 min) - Land on populated dashboard with your first project

---

## 🔧 Method 2: Direct Route Testing

If you want to test individual components:

### Test Welcome Page
- URL: `http://127.0.0.1:5000/onboarding/start`
- Should show: Welcome card with "Start Your Investment Journey" button

### Test Individual Steps
- Step 1: `http://127.0.0.1:5000/onboarding/step/1`
- Step 2: `http://127.0.0.1:5000/onboarding/step/2`
- Step 3: `http://127.0.0.1:5000/onboarding/step/3`

### Test API Endpoints
```bash
# Get onboarding progress
curl -X GET http://127.0.0.1:5000/onboarding/api/progress

# Start onboarding
curl -X POST http://127.0.0.1:5000/onboarding/start
```

---

## 🎯 What to Look For

### Visual Experience
- ✅ Beautiful, responsive design with Bootstrap styling
- ✅ Progress indicators showing step X of 5
- ✅ Timer showing target time for each step
- ✅ Smooth transitions between steps

### Functional Experience
- ✅ Company name gets captured and used throughout
- ✅ Kill checklist actually evaluates answers
- ✅ Different outcomes for "killed" vs "survived" ideas
- ✅ Research template gets created with real workflow steps
- ✅ Dashboard shows actual projects and tools

### Data Persistence
- ✅ OnboardingProgress tracks each step completion
- ✅ User's first company gets created in database
- ✅ Kill checklist with criteria gets generated
- ✅ Research template with workflow steps gets created
- ✅ Research project links company + template

---

## 🐛 Troubleshooting

### If You Get Login Errors
```bash
# Create a test user first
source venv/bin/activate
python -c "
from app import create_app, db
from app.models import User
app = create_app()
with app.app_context():
    user = User(username='testuser', email='test@example.com')
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    print('Test user created: testuser / password123')
"
```

### If Templates Don't Load
- Check that `app/onboarding/templates/onboarding/` directory exists
- Verify all HTML files are present
- Check Flask app can find the templates

### If Routes Don't Work
- Verify onboarding blueprint is registered in `app/__init__.py`
- Check for any import errors in routes.py
- Ensure database migration was applied successfully

---

## 📱 Expected User Experience

### Before Onboarding
- Empty or basic dashboard
- No personalized content
- Generic investment tools

### After Onboarding (10 minutes later)
- Personalized dashboard with their company
- First research project ready to work on
- Kill checklist with their evaluation
- Research template with structured workflow
- Sense of having a "system" not just tools

The transformation should feel like going from "I don't know where to start" to "I have a clear plan and the tools to execute it."