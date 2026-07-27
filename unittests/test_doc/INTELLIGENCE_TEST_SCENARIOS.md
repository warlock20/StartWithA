# Intelligence Engine Test Scenarios

## Setup

1. **Generate test data:**
   ```bash
   python tests/create_intelligence_test_data.py
   ```

2. **Start the application:**
   ```bash
   flask run
   ```

3. **Login:**
   - Email: `intelligence_test@example.com`
   - Password: `testpassword123`

---

## Test Scenarios

### ✅ **Feature 1: Portfolio Conflict Checks**

#### **Test 1.1: Position Concentration Warning**
**Objective:** Trigger position concentration warning

**Steps:**
1. Go to "Add Transaction" page
2. Select company: **AAPL** (already 30% of portfolio)
3. Enter BUY transaction: $50,000
4. **Expected Result:**
   - ⚠️ HIGH severity warning: "Position Concentration Risk"
   - Message shows AAPL will be >40% of portfolio

---

#### **Test 1.2: Sector Concentration Warning**
**Objective:** Trigger sector concentration warning

**Steps:**
1. Go to "Add Transaction" page
2. Select any Technology company: **AAPL**, **MSFT**, or create new tech stock
3. Enter BUY transaction: $30,000
4. **Expected Result:**
   - ⚠️ MEDIUM/HIGH severity warning: "Technology Sector Concentration"
   - Message shows Technology sector already >40% of portfolio

---

#### **Test 1.3: High Correlation Warning**
**Objective:** Trigger industry/sector correlation warning

**Steps:**
1. Go to "Add Transaction" page
2. Create NEW company in Technology sector (e.g., "CRM" - Salesforce)
3. Enter BUY transaction: $10,000
4. **Expected Result:**
   - ⚠️ MEDIUM severity warning: "Same Industry Concentration" or "Sector Overlap"
   - Message shows you already own 2+ Technology positions

---

#### **Test 1.4: Thesis Conflict Warning**
**Objective:** Trigger conflicting thesis warning (if implemented)

**Steps:**
1. Create company with bearish thesis on Technology sector
2. Try to buy more AAPL (bullish on Technology)
3. **Expected Result:**
   - ⚠️ MEDIUM severity warning: "Potential Thesis Conflict"

---

### ✅ **Feature 2: Behavioral Pattern Detection**

#### **Test 2.1: Buying After Run-Up**
**Objective:** Trigger FOMO buying warning

**Steps:**
1. Find a stock that has gone up >20% in 30 days (check yfinance)
2. Try to buy it
3. **Expected Result:**
   - ⚠️ MEDIUM/HIGH severity warning: "Buying After Strong Run-Up"
   - Message shows run-up percentage and days

**Note:** Requires `yfinance` installed and internet connection

---

#### **Test 2.2: Chasing Returns**
**Objective:** Trigger "adding to hot position" warning

**Steps:**
1. Go to "Add Transaction" page
2. Select company: **AAPL** (currently up 20%)
3. Enter BUY transaction to add to position: $10,000
4. **Expected Result:**
   - ⚠️ MEDIUM severity warning: "Adding to Hot Position"
   - Message shows CAGR and asks if chasing performance

---

#### **Test 2.3: Averaging Down**
**Objective:** Trigger averaging down warning

**Setup:** First, create a losing position
1. Create new company (e.g., "SNAP")
2. Buy $10,000 worth
3. Manually update position to show -20% loss
4. Try to buy MORE of the same stock

**Expected Result:**
- ⚠️ HIGH severity warning: "Repeated Averaging Down"
- Message warns about adding to losing position

---

#### **Test 2.4: Overconfidence Pattern**
**Objective:** Trigger overconfidence detection

**Steps:**
1. The test data already has overconfidence pattern:
   - TSLA: Confidence 10, Loss -25%
   - PLTR: Confidence 9, Loss -18.5%
2. Try to buy ANY new stock with confidence 8+
3. **Expected Result:**
   - ⚠️ MEDIUM severity warning: "Overconfidence Pattern Detected"
   - Message shows high-confidence trades have poor outcomes

---

### ✅ **Feature 3: Claude Thesis Analysis**

#### **Test 3.1: Real-Time Thesis Feedback (Quick Check)**
**Objective:** Test live thesis quality feedback

**Steps:**
1. Go to "Add Transaction" page
2. Start typing in "Investment Thesis" field:
   ```
   This is a short thesis.
   ```
3. **Expected Result:**
   - Real-time feedback panel appears
   - Shows: "Too brief" warning, word count, missing elements
   - Updates as you type

---

#### **Test 3.2: Full AI Thesis Analysis**
**Objective:** Test comprehensive AI analysis

**Steps:**
1. Go to "Add Transaction" page
2. Write a detailed thesis (100+ words):
   ```
   NVIDIA is positioned to dominate AI chip market.
   Data center demand is accelerating with ChatGPT and
   other LLMs requiring massive compute. Gaming revenue
   is stable. Market leadership in GPU technology is
   unmatched. Management execution has been stellar.
   ```
3. Click **"Analyze Thesis with AI"** button
4. **Expected Result:**
   - AI analysis appears with:
     - Quality Score (0-100)
     - Grade (A/B/C/D/F)
     - Strengths
     - Weaknesses
     - Missing elements
     - Suggested questions
     - Detected biases (if any)

---

#### **Test 3.3: Weak Thesis Warning in Transaction Check**
**Objective:** Trigger thesis quality warning during transaction

**Steps:**
1. Create new company
2. Add very short thesis: "Good company, will go up"
3. Enter BUY transaction: $5,000
4. **Expected Result:**
   - ⚠️ HIGH severity warning: "Thesis Too Brief"
   - Or: ⚠️ MEDIUM severity warning: "Weak Investment Thesis"
   - Shows quality score, weaknesses, suggested improvements

---

#### **Test 3.4: Strong Thesis Positive Feedback**
**Objective:** Get positive feedback for well-researched thesis

**Steps:**
1. Write comprehensive thesis with:
   - Financial analysis
   - Competitive advantages
   - Risks
   - Valuation rationale
   - Exit criteria
2. Enter transaction
3. **Expected Result:**
   - ℹ️ INFO severity: "Well-Researched Thesis"
   - Shows quality score ≥80, grade A/B, strengths

---

#### **Test 3.5: Bias Detection Warning**
**Objective:** Trigger cognitive bias detection

**Steps:**
1. Write thesis with obvious biases:
   ```
   Elon Musk is a genius and Tesla will OBVIOUSLY dominate
   electric vehicles. Everyone knows this. The stock price
   will definitely 10x. There are no risks because Tesla
   is the future. Anyone who disagrees is stupid.
   ```
2. Enter transaction
3. **Expected Result:**
   - ⚠️ LOW/MEDIUM severity warning: "Potential Cognitive Biases Detected"
   - Shows detected biases: Confirmation Bias, Overconfidence, etc.

---

### ✅ **Feature 4: Similar Past Mistakes (Embeddings)**

#### **Test 4.1: Similar Losses Pattern**
**Objective:** Trigger warning based on similar past losses

**Steps:**
1. Go to "Add Transaction" page
2. Create NEW company in AI/Semiconductor space (e.g., "ARM")
3. Write thesis similar to past losses:
   ```
   ARM is positioned to dominate AI chip market.
   Mobile and data center growth accelerating.
   Technology leadership in energy-efficient processors.
   AI demand will drive revenue growth.
   ```
4. Enter BUY transaction: $10,000
5. **Expected Result:**
   - ⚠️ HIGH severity warning: "Similar Theses Led to Losses"
   - Message shows 3 similar past decisions (NVDA, AMD, INTC) with avg loss -12%
   - Or: "History Suggests Caution" warning

---

#### **Test 4.2: Success Pattern Recognition**
**Objective:** Get positive feedback from similar past successes

**Steps:**
1. Create NEW company in Consumer sector (e.g., "WMT" - Walmart)
2. Write thesis similar to COST/TGT:
   ```
   Walmart has strong customer loyalty and pricing power.
   Omnichannel strategy improving. E-commerce growth
   complementing store sales. Value proposition resonates
   with consumers.
   ```
3. Enter transaction
4. **Expected Result:**
   - ℹ️ INFO severity: "Similar Theses Have Worked"
   - Message shows 2 similar past successes with avg +21%

---

#### **Test 4.3: Overconfidence History Pattern**
**Objective:** Trigger overconfidence history warning

**Steps:**
1. Write a thesis with high confidence (8-10)
2. Use language similar to TSLA/PLTR losses:
   ```
   This company will revolutionize the industry.
   Technology is years ahead. Leadership is visionary.
   This is obviously the future.
   ```
3. Set confidence: 9/10
4. **Expected Result:**
   - ⚠️ MEDIUM severity: "High Confidence Didn't Help"
   - Message shows you had high confidence in 2 similar situations that lost money

---

#### **Test 4.4: Sector Pattern Recognition**
**Objective:** Trigger sector concentration in similar decisions

**Steps:**
1. Create 4th Technology stock
2. Write any tech-related thesis
3. **Expected Result:**
   - ℹ️ LOW severity: "You Often Have Similar Theses in Technology"
   - Shows count and average outcome in that sector

---

#### **Test 4.5: Research Correlation Pattern**
**Objective:** Show if research helped in similar situations

**Setup:** This requires marking some past decisions as "researched"
- Manually link some DecisionJournal entries to ResearchProject

**Expected Result:**
- ℹ️ INFO: "Research Made a Difference"
- Shows researched decisions performed better

---

## Debugging & Troubleshooting

### **Issue: No warnings appear**

**Checks:**
1. Check browser console for JavaScript errors
2. Check Flask logs for backend errors
3. Verify test user has the data:
   ```python
   flask shell
   >>> from app.models import User, DecisionJournal
   >>> user = User.query.filter_by(email='intelligence_test@example.com').first()
   >>> DecisionJournal.query.filter_by(user_id=user.id).count()
   ```

### **Issue: Similar mistakes not working**

**Checks:**
1. Verify embedding service is available:
   ```python
   flask shell
   >>> from app.services.ai.embedding_service import get_embedding_service
   >>> svc = get_embedding_service()
   >>> svc.is_available()
   True
   >>> svc.provider
   'local'  # or 'openai', 'gemini', etc.
   ```

2. Check if embeddings are being generated:
   ```python
   >>> from app.services.ai.embedding_service import embed
   >>> vec = embed("test thesis")
   >>> len(vec)  # Should show dimension (384 for local)
   ```

### **Issue: Thesis analysis not working**

**Checks:**
1. Verify AI service is configured:
   ```python
   flask shell
   >>> from app.services.ai import get_ai_service
   >>> ai = get_ai_service()
   >>> ai.is_available()
   True
   >>> ai.get_available_providers()
   ['gemini', 'claude']  # or similar
   ```

2. Check .env file has API keys:
   ```
   GEMINI_API_KEY=...
   ANTHROPIC_API_KEY=...
   ```

---

## Expected Results Summary

| Feature | Warning Count | Severity Levels |
|---------|--------------|-----------------|
| Portfolio Conflicts | 4-6 warnings | HIGH, MEDIUM |
| Behavioral Patterns | 3-5 warnings | HIGH, MEDIUM, LOW |
| Thesis Analysis | 1-3 warnings | HIGH, MEDIUM, LOW, INFO |
| Similar Mistakes | 2-4 warnings | HIGH, MEDIUM, INFO |

**Total:** 10-18 warnings depending on scenario

---

## Clean Up

To remove test data:
```python
flask shell
>>> from app.models import User
>>> from app import db
>>> user = User.query.filter_by(email='intelligence_test@example.com').first()
>>> # Delete all related data
>>> db.session.delete(user)
>>> db.session.commit()
```
