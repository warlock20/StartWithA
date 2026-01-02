# Behavioral pattern detection system. Here's my comprehensive analysis:

  ---
  1. Constants (app/constants.py) - Lines 168-215 ✓

  Strengths:
  - Excellent organization with clear comments grouping related constants
  - All constants have descriptive docstrings explaining their purpose
  - Threshold values are reasonable and based on behavioral finance research
  - Proper separation between default values and user-customizable settings

  Specific Praise:
  - Winner threshold (15%): Good balance - not too sensitive to noise
  - Early sell days (90 days): Appropriate for identifying premature exits
  - Loser severe threshold (-30%): Correctly identifies material losses
  - Overconfidence rate (40%): Reasonable statistical threshold
  - High confidence score (8/10): Aligns with psychology research on overconfidence

  One Minor Note:
  The DEFAULT_WINNER_MIN_HOLD_DAYS = 30 creates a gap where positions held 30-89 days won't trigger warnings even if sold at 15%+ gain. This is actually correct behavior - you want to avoid warning on legitimate short-term trades.

  ---
  2. Pattern: Selling Winner Early (Lines 886-945) ✓

  Logic Flow:
  1. Fetch active position with current return
  2. Check if it's a winner (≥15% gain)
  3. Validate holding period (≥30 days held, selling before 90 days)
  4. Calculate severity based on gain magnitude and holding period

  Strengths:
  - Proper null checks (if not position, if not position.current_return_pct)
  - Fallback constants if user profile not configured
  - Smart severity escalation (20%+ gain = medium, 30%+ = high)
  - Clear, actionable warning messages with specific metrics

  Potential Edge Case:
  if position.current_return_pct < winner_threshold:
      return None
  This correctly handles the case where a winner has dropped below threshold since purchase. Good defensive programming.

  Verdict: Solid implementation, no changes needed.

  ---
  3. Pattern: Holding Loser Long (Lines 945-1006) ✓

  Logic Flow:
  1. Scan all active positions for losers (≤-15%)
  2. Filter by holding period (≥180 days)
  3. Escalate severity for severe losses or very long holds
  4. Return multiple warnings (one per position)

  Strengths:
  - Handles multiple positions correctly (returns list of warnings)
  - Three-tier severity system:
    - High: Loss ≥30% OR held ≥365 days
    - Medium: Loss 20-30% AND held 180-365 days
    - Low: Loss 15-20% AND held 180-365 days
  - Excellent detail in warning messages (includes days held)

  Smart Design Choice:
  Returns warnings for all qualifying positions, not just the worst one. This is correct - user needs to see all their behavioral blind spots.

  Verdict: Well-designed, comprehensive coverage.

  ---
  4. Pattern: Averaging Down (Lines 758-810) ✓

  Logic Flow:
  1. Count previous BUY transactions for this position
  2. Check if position is currently losing
  3. Trigger warning on 3rd+ buy into a loser
  4. Escalate severity on 5th+ buy

  Strengths:
  - Correctly excludes the current transaction from count (line 772-774)
  - Proper loss threshold check (current_return_pct <= -10)
  - Clear escalation path (medium → high severity)
  - Detailed warning includes number of previous buys

  Excellent Detail:
  if buy_count >= severe_threshold:
      severity = 'High'
      message = f"This is your {buy_count + 1}th purchase into {company.name}..."
  The + 1 correctly represents the transaction being considered, not just past buys.

  Minor Observation:
  Uses -10% hardcoded instead of a constant. This is fine since it's different from the DEFAULT_LOSER_THRESHOLD_PCT (-15%), but consider adding DEFAULT_AVERAGING_DOWN_LOSS_THRESHOLD = -10.0 for consistency.

  Verdict: Logic is sound, works as intended.

  ---
  5. Pattern: Overconfidence Detection (Lines 811-886) ✓

  Logic Flow:
  1. Fetch completed trades with high confidence (≥8/10)
  2. Count trades with poor outcomes (≤-10% return)
  3. Calculate poor outcome rate
  4. Warn if >40% of high-confidence trades performed poorly

  Strengths:
  - Statistical approach: Requires ≥5 trades before analyzing (good sample size)
  - Clear definition of failure: -10% return is objectively poor
  - Appropriate threshold: 40% failure rate indicates systematic overconfidence
  - Educational message: Explains the mismatch between confidence and outcomes

  Smart SQL Query:
  .filter(
      PortfolioTransaction.transaction_type == 'BUY',
      PortfolioTransaction.user_confidence >= high_confidence_score,
      ...
      or_(
          PortfolioTransaction.outcome_return_pct.isnot(None),
          PortfolioTransaction.outcome_return_pct <= poor_outcome_pct
      )
  )
  Correctly filters for completed trades with recorded outcomes.

  Potential Enhancement Opportunity:
  Currently checks ALL historical trades. You could add a recency filter (e.g., last 12 months) to catch evolving patterns, but the current implementation is valid.

  Verdict: Statistically sound, correctly implemented.

  ---
  6. API Endpoint (app/portfolio/routes.py Lines 1593-1607) ✓

  @portfolio_bp.route('/api/check-sell-warnings', methods=['POST'])
  @login_required
  def check_sell_transaction_warnings():
      data = request.get_json()
      company_id = data.get('company_id')
      shares = data.get('shares')

      warnings = check_sell_warnings(current_user.id, company_id, shares) if company_id and shares else []

      return jsonify({
          'warnings': [w.__dict__ for w in warnings],
          'count': len(warnings)
      })

  Strengths:
  - Proper @login_required protection
  - Clean JSON request/response handling
  - Null safety with conditional check
  - Returns empty array if invalid input (graceful degradation)