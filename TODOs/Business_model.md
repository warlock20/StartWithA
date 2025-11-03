 Phase 1: Basic Auth0 Integration (1-2 days)

  What we'll do:
  1. Create Auth0 account (free)
  2. Install authlib or auth0-python
  3. Configure Auth0 application
  4. Update User model to store Auth0 IDs
  5. Replace current login/signup with Auth0
  6. Keep existing users working (migration strategy)

  Code changes:
  # New routes
  @auth_bp.route('/callback')  # Auth0 callback
  @auth_bp.route('/login')     # Redirect to Auth0
  @auth_bp.route('/logout')    # Clear session

  Phase 2: Social Logins (same day)

  Enable in Auth0 dashboard (no code needed!):
  - ✅ Google
  - ✅ GitHub
  - ✅ Microsoft

  Users can choose their preferred login method.

  Phase 3: Freemium Limits (1 day)

  Add subscription tracking to User model:
  class User(db.Model):
      # ... existing fields ...
      auth0_id = db.Column(db.String(255), unique=True)
      subscription_tier = db.Column(db.String(20), default='free')
      # 'free', 'pro', 'team'
      subscription_status = db.Column(db.String(20), default='active')
      companies_limit = db.Column(db.Integer, default=5)
      sectors_limit = db.Column(db.Integer, default=2)

  Phase 4: Usage Tracking & Limits (1 day)

  Enforce limits:
  @companies_bp.route('/add')
  @requires_within_limit('companies')
  def add_company():
      # Check if user has reached limit
      if not current_user.can_add_company():
          flash('Upgrade to Pro for unlimited companies!', 'warning')
          return redirect(url_for('billing.upgrade'))

 
 ---
  Auth0 + Freemium Architecture

  Free Tier (Auth0 Free + Your Free Features)

  User signs up with Auth0 (Google/GitHub/Email)
      ↓
  Auth0 creates user + returns JWT
      ↓
  Your app creates User record (subscription_tier='free')
      ↓
  User gets: 5 companies, 2 sectors, no AI

  Pro Tier (Auth0 Free + Stripe)

  User clicks "Upgrade to Pro"
      ↓
  Stripe checkout ($12/month)
      ↓
  Webhook updates user.subscription_tier = 'pro'
      ↓
  User gets: Unlimited + AI features

  ---
  Cost Breakdown (Your Side)

  With Auth0:

  Per 100 users:
  - Auth0: $0 (free tier)
  - Your hosting: ~$15/month
  - Database: ~$10/month
  - Total: $25/month

  Per 1,000 users:
  - Auth0: $0 (still free!)
  - Your hosting: ~$50/month
  - Database: ~$30/month
  - Total: $80/month

  At 7,500 users:
  - Auth0: $0 (max free tier)
  - Your hosting: ~$200/month
  - Database: ~$100/month
  - Total: $300/month

  Beyond 7,500 users: You'll be making $$$ from Pro subscriptions, so the extra Auth0 cost is worth it!

  ---
  Recommended Freemium Model with Auth0

  🆓 FREE TIER

  Sign up with: Google, GitHub, or Email (via Auth0)

  Includes:
  - ✅ 5 companies
  - ✅ 2 sectors
  - ✅ All core research tools
  - ✅ Kill Checklist
  - ✅ Too Hard Basket
  - ✅ Basic analytics
  - ❌ No AI features
  - ❌ No exports

  💎 PRO TIER ($12/month)

  Everything in Free, plus:
  - ✅ Unlimited companies & sectors
  - ✅ AI summaries (you pay for Gemini API)
  - ✅ PDF/Markdown exports
  - ✅ Premium templates
  - ✅ Advanced analytics

  ---
  Implementation Timeline

  Week 1: Auth0 Integration
  - Day 1-2: Set up Auth0, integrate login/signup
  - Day 3: Test social logins (Google, GitHub)
  - Day 4: Migrate existing users (if any)
  - Day 5: Polish UI, add user profile

  Week 2: Freemium + Payments
  - Day 1: Add subscription fields to User model
  - Day 2: Implement usage limits & tracking
  - Day 3: Add "Upgrade" prompts in UI
  - Day 4-5: Integrate Stripe for payments

  Total: ~10 days for complete system

  ---
  Should We Do This Now?

  ✅ YES, implement Auth0 if:

  - You want easier onboarding (social login = less friction)
  - You want to scale without security headaches
  - You're ready to start getting users
  - Auth0 free tier covers your needs (7,500 users!)

  ❌ WAIT if:

  - You're still fixing core bugs
  - No one is asking for the product yet
  - You want to focus on features first

  ---
  My Recommendation

  Do this in phases:

  Phase 1 (This week): Auth0 Only

  - Replace current auth with Auth0
  - Enable Google + GitHub login
  - Don't add limits yet - everyone gets full access
  - Get users, collect feedback

  Phase 2 (Next month): Add Freemium

  - Once you have 20-50 active users
  - Add usage limits for new signups
  - Grandfather existing users (give them Pro free for 6 months)
  - Integrate Stripe

  Phase 3 (Later): Polish

  - Team tier
  - Advanced features
  - Scale infrastructure

  ---
  Want me to start implementing Auth0 integration? I can:

  1. Just plan it (architecture document)
  2. Implement Auth0 (replace current auth)
  3. Full freemium (Auth0 + limits + Stripe)


  Please follow these steps:

  1. Go to Auth0: https://auth0.com/signup
  2. Sign up for free (use Google or GitHub for fastest signup)
  3. Create a tenant (e.g., "investment-checklist" or your app name)
  4. Create a Regular Web Application:
    - Dashboard → Applications → Create Application
    - Name: "Investment Checklist Platform"
    - Type: Regular Web Application
    - Click "Create"
  5. Get your credentials:
    - Go to your application settings
    - Copy these values (we'll need them):
        - Domain (e.g., dev-xxx.us.auth0.com)
      - Client ID
      - Client Secret
  6. Configure Callback URLs:
    - Allowed Callback URLs: http://localhost:5000/auth/callback, http://127.0.0.1:5000/auth/callback
    - Allowed Logout URLs: http://localhost:5000, http://127.0.0.1:5000
    - Allowed Web Origins: http://localhost:5000, http://127.0.0.1:5000
    - Click "Save Changes"

  Once you have your Auth0 credentials ready, let me know and I'll proceed with the code integration!

  Should I wait for you to set this up, or would you like me to continue with the code while you do this in parallel?