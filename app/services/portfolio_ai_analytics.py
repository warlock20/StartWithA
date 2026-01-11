"""
AI-Powered Portfolio Analytics Service

Integrates:
- PortfolioDataExtractor: Extract transaction/position data
- IntelligenceService: AI analysis via YAML prompts
- Cache: Event-based invalidation (regenerate on new transactions)
"""

import logging
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, date
from pathlib import Path

from app.models.portfolio import Transaction
from app.services.portfolio_data_extractor import PortfolioDataExtractor
from app.services.ai.intelligence_service import IntelligenceService

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = (
    Path(__file__).parent.parent.parent / "instance" / "cache" / "portfolio_insights"
)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class PortfolioAIAnalytics:
    """
    AI-powered portfolio analytics with intelligent caching.

    Usage:
        analytics = PortfolioAIAnalytics(user_id=1)
        insights = analytics.get_insights()
    """

    def __init__(self, user_id: int):
        """Initialize analytics service"""
        self.user_id = user_id
        self.extractor = PortfolioDataExtractor(user_id)
        self.intelligence = IntelligenceService()

    # ================================================================
    # Public API - Main Orchestrator
    # ================================================================

    def get_insights(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive AI-powered portfolio insights.

        This method orchestrates all sub-analyses and combines results.
        For now, only deep behavioral analysis is implemented.

        Future structure:
        {
            'quick_insights': {...},      # Fast overview (future)
            'behavioral': {...},           # Deep behavioral analysis (current)
            'risk_analysis': {...},        # Risk deep dive (future)
            'sector_analysis': {...}       # Sector concentration (future)
        }

        Args:
            force_refresh: Skip cache and regenerate all analyses

        Returns:
            Combined analysis dict with all insights
        """
        logger.info(f"Running portfolio insights for user {self.user_id}")

        # FOR NOW: Using quick insights (portfolio_complete_analysis)
        # because the template expects that structure
        # TODO: Once we update the template, switch to combined results
        return self.get_deep_behavioral_insights(force_refresh)

        # FUTURE: Return combined results from multiple analyses
        # combined_results = {}
        # combined_results['quick'] = self.get_quick_insights(force_refresh)
        # combined_results['behavioral'] = self.get_deep_behavioral_insights(force_refresh)
        # return combined_results

    # ================================================================
    # Sub-Analysis Methods (Modular)
    # ================================================================

    def get_quick_insights(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Quick portfolio overview using pre-calculated metrics.
        Template: portfolio_complete_analysis.yaml

        Fast, high-level summary suitable for dashboard display.
        """
        template_name = "portfolio_complete_analysis"
        return self._run_analysis(template_name, force_refresh)

    def get_deep_behavioral_insights(
        self, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Deep behavioral analysis from raw transaction history.
        Template: portfolio_raw_trade_analysis.yaml

        Analyzes:
        - FOMO patterns and triggers
        - Tax optimization opportunities
        - Investor evolution over time
        - Behavioral biases (disposition effect, recency bias)
        """
        template_name = "portfolio_raw_trade_analysis"
        return self._run_analysis(template_name, force_refresh)

    # ================================================================
    # Insight Generation (Internal)
    # ================================================================

    def _run_analysis(
        self, template_name: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Run a specific analysis using the given template.
        Handles caching per template.

        Args:
            template_name: Name of YAML template to use
            force_refresh: Skip cache and run fresh analysis

        Returns:
            Analysis results or placeholder if no cache and not forced
        """
        # Check cache first
        cached = self._get_cached_insights(template_name)

        # If force_refresh is False and no cache exists, return placeholder
        # TODO: After testing, uncomment the auto-generation logic below
        if not force_refresh:
            if cached:
                logger.info(f"Using cached {template_name} for user {self.user_id}")
                return cached
            else:
                # No cache and not forcing refresh - return placeholder
                logger.info(
                    f"No cache for {template_name}, user must click 'Re-run Analysis'"
                )
                return self._get_placeholder_response(template_name)

        # Force refresh requested - generate fresh insights
        logger.info(
            f"Generating fresh {template_name} insights for user {self.user_id}"
        )
        insights = self._generate_insights(template_name)

        # Cache result
        self._cache_insights(insights, template_name)

        return insights

    def _generate_insights(self, template_name: str) -> Dict[str, Any]:
        """Generate fresh AI insights using IntelligenceService + YAML prompt"""

        # 1. Extract portfolio data
        portfolio_data = self.extractor.extract_all()

        # Check sufficient data
        if not portfolio_data["metadata"]["has_data"]:
            return self._get_insufficient_data_response(portfolio_data)

        # 2. Prepare variables based on template type
        variables = self._prepare_template_variables(template_name, portfolio_data)

        # 3. Call IntelligenceService with specified template
        try:
            # Load template
            template = self.intelligence._load_prompt_template(template_name)
            if not template:
                logger.error("Template returned None")
                return self._get_fallback_insights(portfolio_data)

            # Get config (provider, model, etc.)
            config = self.intelligence._get_task_config(template_name, template)

            # Format prompt with variables
            prompt = self.intelligence._format_prompt(template, variables)

            # Log the prompt for debugging
            logger.info(f"=" * 80)
            logger.info(f"PROMPT FOR {template_name}:")
            logger.info(f"-" * 80)
            logger.info(prompt)
            logger.info(f"=" * 80)

            # Get provider with specific model (will raise RuntimeError if none available)
            provider = self.intelligence._get_provider(
                config["provider"],
                config.get("model")
            )

            # Call provider to generate insights
            ai_insights = self.intelligence._call_provider_to_generate_json(provider, prompt, config)

            # Log the structured response
            logger.info(f"=" * 80)
            logger.info(f"STRUCTURED JSON RESPONSE FROM {config['provider']}:")
            logger.info(f"-" * 80)
            logger.info(f"Keys: {list(ai_insights.keys())}")
            logger.info(f"=" * 80)

            # Save raw response to file for debugging
            debug_file = CACHE_DIR / f"user_{self.user_id}_{template_name}_structured_response.json"
            try:
                with open(debug_file, 'w') as f:
                    json.dump(ai_insights, f, indent=2, default=str)
                logger.info(f"Structured raw AI response to {debug_file}")
            except Exception as e:
                logger.warning(f"Failed to save raw response: {e}")

            # Parse response
            # ai_insights = self.intelligence._parse_response(response, template)
            # if not ai_insights:
            #     logger.error("AI response parsing returned None")
            #     return self._get_fallback_insights(portfolio_data)

            # # Log parsed insights structure for debugging
            # logger.info(f"=" * 80)
            # logger.info(f"PARSED AI INSIGHTS STRUCTURE:")
            # logger.info(f"-" * 80)
            # logger.info(f"Keys: {list(ai_insights.keys())}")
            # logger.info(f"=" * 80)

            # Save parsed structure to file for debugging
            # parsed_file = CACHE_DIR / f"user_{self.user_id}_{template_name}_parsed_structure.json"
            # try:
            #     with open(parsed_file, 'w') as f:
            #         json.dump(ai_insights, f, indent=2, default=str)
            #     logger.info(f"Saved parsed structure to {parsed_file}")
            # except Exception as e:
            #     logger.warning(f"Failed to save parsed structure: {e}")

            # Normalize AI response structure (handle different wrappers)
            normalized_insights = self._normalize_ai_response(ai_insights)

            # Format for template
            formatted_insights = self._format_for_template(normalized_insights, portfolio_data)

            return formatted_insights

        except RuntimeError as e:
            # No AI provider available
            logger.warning(f"No AI provider available: {e}")
            return self._get_fallback_insights(portfolio_data)
        except Exception as e:
            logger.error(f"Failed to generate portfolio insights: {e}", exc_info=True)
            return self._get_fallback_insights(portfolio_data)

    def _prepare_template_variables(
        self, template_name: str, portfolio_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare variables for template based on template type.

        Different templates need different data formats:
        - portfolio_complete_analysis: Pre-calculated metrics (summary stats)
        - portfolio_raw_trade_analysis: Raw transactions (chronological trades)

        Args:
            template_name: Name of template
            portfolio_data: Extracted portfolio data

        Returns:
            Variables dict for template
        """
        if template_name == "portfolio_complete_analysis":
            # Pre-calculated metrics for quick overview
            # Format as natural text instead of JSON to avoid recitation filter
            summary = portfolio_data["portfolio_summary"]
            patterns = portfolio_data["trading_patterns"]

            return {
                "portfolio_summary": f"""
                - Total positions: {summary.get('total_positions', 0)}
                - Closed positions: {summary.get('closed_positions', 0)}
                - Total invested: ${summary.get('total_invested', 0):,.2f}
                - Win rate: {summary.get('win_rate', 0):.1f}%
                """,
                "trading_patterns": f"""
                - Average holding period: {patterns.get('avg_hold_days', 0):.0f} days
                - Winner avg return: {patterns.get('avg_winner_return', 0):.1f}%
                - Loser avg return: {patterns.get('avg_loser_return', 0):.1f}%
                """,
                "sector_breakdown": self._format_sectors_text(
                    portfolio_data["sector_breakdown"][:5]
                ),
                "positions": self._format_positions_text(
                    portfolio_data["positions"][:5]
                ),
                "closed_positions": self._format_positions_text(
                    portfolio_data["closed_positions"][:5]
                ),
                "recent_activity": self._format_activity_text(
                    portfolio_data["recent_activity"][:10]
                ),
            }

        elif template_name == "portfolio_raw_trade_analysis":
            # Raw transactions for behavioral analysis
            transactions = self.extractor.extract_transactions()

            # Get user profile data (tax residence)
            from app.models.user import User

            user = User.query.get(self.user_id)
            tax_residence = (
                user.tax_residence
                if user and hasattr(user, "tax_residence")
                else "Germany"
            )

            # Calculate analysis period
            if transactions:
                first_date = min(t["date"] for t in transactions)
                last_date = max(t["date"] for t in transactions)
                analysis_period = f"{first_date} to {last_date}"
            else:
                analysis_period = "No transactions"
            
            return {
                "tax_residence": tax_residence,
                "analysis_period": analysis_period,
                "transaction_count": len(transactions),
                "transactions_text": self._format_transactions_text(
                    transactions
                ),  # Human-friendly chronological transactions
            }

        else:
            raise ValueError(f"Unknown template type: {template_name}")

    def _format_sectors_text(self, sectors: list) -> str:
        """Format sector breakdown as natural text"""
        if not sectors:
            return "No sector data available"

        lines = []
        for sector in sectors:
            lines.append(
                f"- {sector['sector']}: {sector['percentage']:.1f}% (${sector['total_cost']:,.2f})"
            )
        return "\n".join(lines)

    def _format_positions_text(self, positions: list) -> str:
        """Format positions as natural text"""
        if not positions:
            return "No positions"

        lines = []
        for pos in positions[:5]:  # Top 5 only
            ticker = pos.get("ticker", "Unknown")
            sector = pos.get("sector", "Unknown")
            invested = pos.get("total_invested", 0)
            lines.append(f"- {ticker} ({sector}): ${invested:,.2f}")
        return "\n".join(lines)

    def _format_activity_text(self, activities: list) -> str:
        """Format recent activity as natural text"""
        if not activities:
            return "No recent activity"

        lines = []
        for act in activities[:10]:
            date = act.get("date", "Unknown")
            action = act.get("type", "Unknown")
            ticker = act.get("ticker", "Unknown")
            lines.append(f"- {date}: {action} {ticker}")
        return "\n".join(lines)

    def _format_transactions_text(self, transactions: list) -> str:
        """Format raw transactions into simple human-readable chronological lines.

        Expected transaction dict keys (best-effort):
        - date (ISO string or date)
        - type/action (e.g., BUY, SELL)
        - ticker
        - exec_price or price
        - quantity or shares
        - fee (optional)
        - note/log (optional)
        """
        if not transactions:
            return "No transactions"

        lines = []
        for tx in transactions:
            # Date
            tx_date = (
                tx.get("date") or tx.get("transaction_date") or tx.get("created_at")
            )
            # Normalize date to YYYY-MM-DD if it's a datetime/date object
            try:
                if isinstance(tx_date, (datetime, date)):
                    tx_date = (
                        tx_date.date().isoformat()
                        if isinstance(tx_date, datetime)
                        else tx_date.isoformat()
                    )
            except Exception:
                # leave as-is
                pass

            # Action / type
            action = (
                tx.get("type") or tx.get("action") or tx.get("side") or ""
            ).upper() or "TRADE"

            # Ticker
            ticker = tx.get("ticker") or tx.get("symbol") or "UNKNOWN"

            # Price
            price = tx.get("exec_price") or tx.get("price") or tx.get("proceeds")
            price_str = (
                f"{price:.2f}"
                if isinstance(price, (int, float))
                else (str(price) if price is not None else "N/A")
            )

            # Quantity
            qty = (
                tx.get("quantity")
                or tx.get("shares")
                or tx.get("qty")
                or tx.get("amount")
            )
            qty_str = f"{qty}" if qty is not None else "N/A"

            # Fee (optional)
            fee = tx.get("fee")
            fee_str = (
                f" (fee ${fee:.2f})"
                if isinstance(fee, (int, float))
                else (" (" + str(fee) + ")" if fee is not None else "")
            )

            # Build line in natural language (avoid database-like format to prevent recitation filter)
            # OLD FORMAT (triggers recitation): "2020-01-15 | BUY | AAPL | 150.00 | 10"
            # NEW FORMAT (natural): "On 2020-01-15: Bought 10 shares of AAPL at $150.00"

            if action == 'BUY':
                verb = 'Bought'
            elif action == 'SELL':
                verb = 'Sold'
            elif action == 'DIVIDEND':
                verb = 'Received dividend on'
            else:
                verb = action.capitalize()

            line = f"On {tx_date}: {verb} {qty_str} shares of {ticker} at ${price_str}"

            if fee_str:
                line += f" {fee_str}"

            # Optional note
            note = tx.get("note") or tx.get("log") or tx.get("memo")
            if note:
                line = f"{line} (Note: {note})"

            lines.append(line)

        return "\n".join(lines)

    def _normalize_ai_response(self, ai_insights: Dict[str, Any]) -> Dict[str, Any]:
      """Normalize AI response - handles both schema-based and free-form responses"""

      logger.info(f"Normalizing AI response with top-level keys: {list(ai_insights.keys())}")

      # If response follows the new schema structure
      if "investor_behavior_analysis" in ai_insights:
          logger.info("Detected schema-based response structure")
          analysis = ai_insights["investor_behavior_analysis"]

          return {
              "overall_assessment": analysis.get("summary", ""),
              "behavioral_patterns": self._extract_behavioral_patterns(analysis.get("behavioral_patterns", [])),
              "fomo_analysis": self._extract_fomo_analysis(analysis.get("fomo_analysis", {})),
              "investor_evolution": self._extract_evolution(analysis.get("evolution_timeline", [])),
              "recommendations": [],  # Will be added if in schema
              "key_strengths": analysis.get("key_findings", []),
              "key_risks": []
          }
    
    
    # def _normalize_ai_response(self, ai_insights: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Normalize AI response to expected structure.

    #     Different AI models may wrap responses differently:
    #     - {"investor_analysis": {...}} -> unwrap
    #     - {"overall_assessment": ...} -> use as-is

    #     Expected output structure:
    #     {
    #         "overall_assessment": str,
    #         "behavioral_patterns": list,
    #         "fomo_analysis": str or dict,
    #         "investor_evolution": str,
    #         "recommendations": list
    #     }
    #     """
    #     # Log the incoming structure for debugging
    #     logger.info(f"Normalizing AI response with top-level keys: {list(ai_insights.keys())}")

    #     # Special case: If response is wrapped in 'response' key with text (JSON parsing failed)
    #     # Try to parse it again, stripping markdown code fences
    #     if len(ai_insights) == 1 and 'response' in ai_insights and isinstance(ai_insights['response'], str):
    #         logger.warning("Response wrapped in 'response' key as string, attempting to parse JSON")
    #         try:
    #             # Strip markdown code fences if present
    #             response_text = ai_insights['response'].strip()

    #             # Remove ```json or ``` at start and end
    #             if response_text.startswith('```'):
    #                 # Find the first newline after opening fence
    #                 first_newline = response_text.find('\n')
    #                 if first_newline > 0:
    #                     response_text = response_text[first_newline + 1:].strip()

    #             if response_text.endswith('```'):
    #                 response_text = response_text[:-3].strip()

    #             logger.info(f"Cleaned response text, length: {len(response_text)}")
    #             logger.info(f"First 100 chars: {response_text[:100]}")

    #             # Try to parse the cleaned response string as JSON
    #             reparsed = json.loads(response_text)
    #             if isinstance(reparsed, dict):
    #                 ai_insights = reparsed
    #                 logger.info(f"Successfully reparsed JSON, new keys: {list(ai_insights.keys())}")
    #         except json.JSONDecodeError as e:
    #             logger.error(f"Failed to reparse JSON from response string: {e}")
    #             # Continue with the original structure

    #     # If wrapped in a single key, unwrap it
    #     if len(ai_insights) == 1:
    #         wrapper_key = list(ai_insights.keys())[0]
    #         if isinstance(ai_insights[wrapper_key], dict):
    #             # Unwrap: {"investor_analysis": {...}} -> {...}
    #             ai_insights = ai_insights[wrapper_key]
    #             logger.info(f"Unwrapped AI response from '{wrapper_key}' key, new keys: {list(ai_insights.keys())}")

    #     # Map different possible keys to expected structure
    #     normalized = {}

    #     # Overall assessment (multiple possible keys)
    #     # Try to extract from nested structures if not found at top level
    #     overall_assessment = (
    #         ai_insights.get("overall_assessment") or
    #         ai_insights.get("summary") or
    #         ai_insights.get("analysis")
    #     )

    #     # If not found, try to extract from nested pattern objects
    #     if not overall_assessment:
    #         # Look for any nested dict that might contain the assessment
    #         for key, value in ai_insights.items():
    #             if isinstance(value, dict):
    #                 if "summary" in value:
    #                     overall_assessment = value["summary"]
    #                     logger.info(f"Found summary in nested key '{key}'")
    #                     break
    #                 elif "description" in value:
    #                     overall_assessment = value["description"]
    #                     logger.info(f"Found description in nested key '{key}'")
    #                     break

    #     normalized["overall_assessment"] = overall_assessment or "No overall assessment available."

    #     # Behavioral patterns (may be nested)
    #     patterns_raw = (
    #         ai_insights.get("behavioral_patterns") or
    #         ai_insights.get("first_key_behavioral_patterns") or
    #         ai_insights.get("key_patterns")
    #     )

    #     # If not found at top level, look for nested pattern structures
    #     if not patterns_raw:
    #         for key, value in ai_insights.items():
    #             if isinstance(value, dict) and ("patterns" in key.lower() or "bias" in key.lower()):
    #                 logger.info(f"Found patterns in nested key '{key}'")
    #                 # Extract the pattern dict and convert to list format
    #                 patterns_raw = [{
    #                     "title": k.replace("_", " ").title(),
    #                     "description": v.get("summary", v.get("description", str(v))) if isinstance(v, dict) else str(v)
    #                 } for k, v in value.items()]
    #                 break

    #     # If it's a dict, extract analysis text
    #     if isinstance(patterns_raw, dict):
    #         normalized["behavioral_patterns"] = [{
    #             "name": "Behavioral Analysis",
    #             "description": patterns_raw.get("analysis", patterns_raw.get("summary", str(patterns_raw)))
    #         }]
    #     elif isinstance(patterns_raw, list):
    #         normalized["behavioral_patterns"] = patterns_raw
    #     else:
    #         normalized["behavioral_patterns"] = []

    #     # FOMO analysis
    #     fomo_raw = (
    #         ai_insights.get("fomo_analysis") or
    #         ai_insights.get("fomo_details") or
    #         ai_insights.get("fomo")
    #     )
    #     if isinstance(fomo_raw, dict):
    #         normalized["fomo_analysis"] = fomo_raw.get("analysis") or str(fomo_raw)
    #     else:
    #         normalized["fomo_analysis"] = fomo_raw or "No FOMO analysis available."

    #     # Investor evolution
    #     evolution_raw = (
    #         ai_insights.get("investor_evolution") or
    #         ai_insights.get("evolution") or
    #         ai_insights.get("progression")
    #     )
    #     if isinstance(evolution_raw, dict):
    #         normalized["investor_evolution"] = evolution_raw.get("analysis") or str(evolution_raw)
    #     else:
    #         normalized["investor_evolution"] = evolution_raw or "No evolution tracking available."

    #     # Recommendations
    #     recs_raw = (
    #         ai_insights.get("recommendations") or
    #         ai_insights.get("advice") or
    #         ai_insights.get("suggestions")
    #     )

    #     # Look for recommendations in nested structures
    #     if not recs_raw:
    #         for key, value in ai_insights.items():
    #             if isinstance(value, dict) and "recommend" in key.lower():
    #                 logger.info(f"Found recommendations in nested key '{key}'")
    #                 if isinstance(value, dict):
    #                     recs_raw = [{"title": k.replace("_", " ").title(), "description": v} for k, v in value.items()]
    #                 else:
    #                     recs_raw = value
    #                 break

    #     if isinstance(recs_raw, dict):
    #         normalized["recommendations"] = [{"title": k, "description": v} for k, v in recs_raw.items()]
    #     elif isinstance(recs_raw, list):
    #         normalized["recommendations"] = recs_raw
    #     elif isinstance(recs_raw, str):
    #         normalized["recommendations"] = [{"title": "Recommendation", "description": recs_raw}]
    #     else:
    #         normalized["recommendations"] = []

    #     # Key strengths (optional)
    #     normalized["key_strengths"] = ai_insights.get("key_strengths", [])

    #     # Key risks (optional)
    #     normalized["key_risks"] = ai_insights.get("key_risks", [])

    #     logger.info(f"Normalized AI response - Keys: {list(normalized.keys())}")
    #     logger.info(f"Normalized data preview:")
    #     logger.info(f"  - overall_assessment: {normalized['overall_assessment'][:100] if normalized['overall_assessment'] else 'None'}...")
    #     logger.info(f"  - behavioral_patterns count: {len(normalized.get('behavioral_patterns', []))}")
    #     logger.info(f"  - recommendations count: {len(normalized.get('recommendations', []))}")

    #     return normalized

    def _format_for_template(
        self, ai_insights: Dict[str, Any], portfolio_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format AI insights and portfolio data for template consumption"""

        summary = portfolio_data["portfolio_summary"]
        patterns = portfolio_data["trading_patterns"]

        # Determine risk level
        tech_concentration = 0
        if portfolio_data["sector_breakdown"]:
            tech_sector = next(
                (
                    s
                    for s in portfolio_data["sector_breakdown"]
                    if s.get("sector") == "Technology"
                ),
                None,
            )
            if tech_sector:
                tech_concentration = tech_sector.get("percentage", 0)

        risk_level = (
            "High"
            if tech_concentration > 50
            else "Medium" if tech_concentration > 30 else "Low"
        )
        risk_description = (
            f"Sector concentration at {tech_concentration}%"
            if tech_concentration > 30
            else "Well diversified"
        )

        # Build formatted structure
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "last_transaction_date": self._get_last_transaction_date(),
                "transactions_count": summary.get("total_transactions", 0),
                "positions_count": summary.get("total_positions", 0),
                "error": None,
            },
            "kpis": {
                "win_rate": round(patterns.get("win_rate", 0), 1),
                "market_avg_win_rate": 52,  # Market average
                "avg_hold_days": round(patterns.get("avg_hold_days", 0)),
                "strategy_label": self._get_strategy_label(
                    patterns.get("avg_hold_days", 0)
                ),
                "positions_count": summary.get("total_positions", 0),
                "sector_concentration": round(tech_concentration, 1),
                "risk_level": risk_level,
                "risk_description": risk_description,
            },
            "ai_summary": {
                "quick_insight": ai_insights.get(
                    "overall_assessment", "Analysis in progress..."
                )[:200]
            },
            "analysis": {
                "overall_assessment": ai_insights.get(
                    "overall_assessment", "No assessment available."
                ),
                "key_strengths": ai_insights.get("key_strengths", []),
                "key_risks": self._format_risks(ai_insights.get("key_risks", [])),
                "behavioral_patterns": self._format_patterns(
                    ai_insights.get("behavioral_patterns", [])
                ),
                "recommendations": self._format_recommendations(
                    ai_insights.get("recommendations", [])
                ),
            },
            "comparison": {
                "winners": {
                    "avg_return": round(patterns.get("avg_winner_return", 0), 1),
                    "hold_time": round(patterns.get("avg_winner_hold_days", 0)),
                    "success_rate": round(patterns.get("win_rate", 0), 1),
                },
                "losers": {
                    "avg_loss": round(patterns.get("avg_loser_return", 0), 1),
                    "hold_time": round(patterns.get("avg_loser_hold_days", 0)),
                    "pattern": "Hold longer",
                    "insight": self._get_disposition_effect_insight(patterns),
                },
            },
        }

    def _get_strategy_label(self, avg_hold_days: float) -> str:
        """Get strategy label based on holding period"""
        if avg_hold_days < 30:
            return "Short-term Trading"
        elif avg_hold_days < 90:
            return "Medium-term Strategy"
        else:
            return "Long-term Strategy"

    def _get_disposition_effect_insight(self, patterns: Dict[str, Any]) -> str:
        """Generate disposition effect insight"""
        winner_days = patterns.get("avg_winner_hold_days", 0)
        loser_days = patterns.get("avg_loser_hold_days", 0)

        if loser_days > winner_days * 1.2:
            pct_longer = round(((loser_days - winner_days) / winner_days) * 100)
            return f"You hold losers {pct_longer}% longer than winners."
        return None

    def _format_risks(self, risks: list) -> list:
        """Format risks for template"""
        formatted = []
        for risk in risks:
            if isinstance(risk, str):
                formatted.append(
                    {
                        "title": risk,
                        "description": risk,
                        "level": "medium",
                        "mitigation": None,
                    }
                )
            elif isinstance(risk, dict):
                formatted.append(
                    {
                        "title": risk.get("title", risk.get("name", "Risk")),
                        "description": risk.get("description", risk.get("detail", "")),
                        "level": risk.get("level", risk.get("severity", "medium")),
                        "mitigation": risk.get(
                            "mitigation", risk.get("solution", None)
                        ),
                    }
                )
        return formatted

    def _format_patterns(self, patterns: list) -> list:
        """Format behavioral patterns for template"""
        formatted = []
        for pattern in patterns:
            if isinstance(pattern, str):
                formatted.append(
                    {
                        "title": pattern,
                        "description": pattern,
                        "severity": None,
                        "icon": "brain",
                        "recommendation": None,
                    }
                )
            elif isinstance(pattern, dict):
                formatted.append(
                    {
                        "title": pattern.get("title", pattern.get("name", "Pattern")),
                        "description": pattern.get(
                            "description", pattern.get("detail", "")
                        ),
                        "severity": pattern.get(
                            "severity", pattern.get("impact", None)
                        ),
                        "icon": pattern.get("icon", "brain"),
                        "recommendation": pattern.get(
                            "recommendation", pattern.get("solution", None)
                        ),
                    }
                )
        return formatted

    def _format_recommendations(self, recommendations: list) -> list:
        """Format recommendations for template"""
        formatted = []
        for rec in recommendations:
            if isinstance(rec, str):
                formatted.append(
                    {"title": rec, "description": rec, "priority": "normal"}
                )
            elif isinstance(rec, dict):
                formatted.append(
                    {
                        "title": rec.get("title", rec.get("action", "Action")),
                        "description": rec.get("description", rec.get("detail", "")),
                        "priority": rec.get("priority", "normal"),
                    }
                )
        return formatted

    def _extract_behavioral_patterns(self, patterns: list) -> list:
        """Convert schema-based patterns to template format"""
        return [{
            "title": p.get("pattern_name", ""),
            "description": p.get("description", ""),
            "severity": None,  # Could derive from description
            "icon": "brain",
            "recommendation": None
        } for p in patterns]
    
    def _extract_fomo_analysis(self, fomo: dict) -> str:
        """Convert FOMO dict to text"""
        definition = fomo.get("definition", "")
        trades = fomo.get("fomo_trades", [])
        # Format as text for display
        return f"{definition}\n\nIdentified {len(trades)} FOMO-driven trades."

    def _extract_evolution(self, timeline: list) -> str:
        """Convert evolution timeline to text"""
        parts = []
        for period in timeline:
            parts.append(f"**{period.get('phase_name', '')} ({period.get('period', '')})**: {period.get('analysis', '')}")
        return "\n\n".join(parts)
    # ================================================================
    # Caching
    # ================================================================

    def _get_cached_insights(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get cached insights if valid.

        Cache is per-template, so each analysis type has its own cache.

        Args:
            template_name: Name of template (used in cache filename)

        Returns:
            Cached data or None if invalid/missing
        """
        cache_file = CACHE_DIR / f"user_{self.user_id}_{template_name}.json"

        if not cache_file.exists():
            logger.info(f"No cache found for {template_name} (user {self.user_id})")
            return None

        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)

            # Check if cache is still valid (no new transactions)
            cached_last_txn_date = cached_data.get("metadata", {}).get(
                "last_transaction_date"
            )
            current_last_txn_date = self._get_last_transaction_date()

            if cached_last_txn_date != current_last_txn_date:
                logger.info(
                    f"Cache invalid for {template_name}: transaction date changed"
                )
                return None

            logger.info(f"Using cached {template_name} for user {self.user_id}")
            return cached_data

        except Exception as e:
            logger.error(f"Failed to load cache for {template_name}: {e}")
            return None

    def _cache_insights(self, insights: Dict[str, Any], template_name: str) -> None:
        """
        Cache insights with metadata.

        Cache invalidation: Stale when new transaction added.

        Args:
            insights: Analysis results to cache
            template_name: Template name (used in cache filename)
        """
        cache_file = CACHE_DIR / f"user_{self.user_id}_{template_name}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump(insights, f, indent=2)
            logger.info(f"Cached {template_name} for user {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to cache {template_name}: {e}")

    def _get_last_transaction_date(self) -> Optional[str]:
        """Get date of most recent transaction (ISO format)"""
        last_txn = (
            Transaction.query.filter_by(user_id=self.user_id)
            .order_by(Transaction.date.desc())
            .first()
        )

        return last_txn.date.isoformat() if last_txn else None

    # ================================================================
    # Fallbacks & Placeholders
    # ================================================================

    def _get_placeholder_response(self, template_name: str) -> Dict[str, Any]:
        """
        Return placeholder when no cache exists and analysis not requested.
        User must click 'Re-run Analysis' to generate insights.
        """
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "last_transaction_date": self._get_last_transaction_date(),
                "transactions_count": 0,
                "positions_count": 0,
                "error": "no_analysis_run",
            },
            "kpis": {
                "win_rate": 0,
                "market_avg_win_rate": 52,
                "avg_hold_days": 0,
                "strategy_label": "No analysis yet",
                "positions_count": 0,
                "sector_concentration": 0,
                "risk_level": "N/A",
                "risk_description": 'Click "Re-run Analysis" to generate AI insights',
            },
            "ai_summary": {
                "quick_insight": 'No analysis has been run yet. Click the "Re-run Analysis" button to generate AI-powered insights.'
            },
            "analysis": {
                "overall_assessment": 'AI analysis has not been run yet. Click the "Re-run Analysis" button above to generate comprehensive portfolio insights.',
                "key_strengths": [],
                "key_risks": [],
                "behavioral_patterns": [],
                "recommendations": [],
            },
            "comparison": {
                "winners": {"avg_return": 0, "hold_time": 0, "success_rate": 0},
                "losers": {
                    "avg_loss": 0,
                    "hold_time": 0,
                    "pattern": "N/A",
                    "insight": None,
                },
            },
        }

    def _get_insufficient_data_response(
        self, portfolio_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Response when no transaction data"""
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "last_transaction_date": None,
                "transactions_count": 0,
                "positions_count": 0,
                "error": "insufficient_data",
            },
            "kpis": {
                "win_rate": 0,
                "market_avg_win_rate": 52,
                "avg_hold_days": 0,
                "strategy_label": "No data",
                "positions_count": 0,
                "sector_concentration": 0,
                "risk_level": "N/A",
                "risk_description": "No data available",
            },
            "ai_summary": {
                "quick_insight": "No transaction data available. Import transactions to begin analysis."
            },
            "analysis": {
                "overall_assessment": "No transaction data available. Import transactions to begin analysis.",
                "key_strengths": [],
                "key_risks": [],
                "behavioral_patterns": [],
                "recommendations": [],
            },
            "comparison": {
                "winners": {"avg_return": 0, "hold_time": 0, "success_rate": 0},
                "losers": {
                    "avg_loss": 0,
                    "hold_time": 0,
                    "pattern": "N/A",
                    "insight": None,
                },
            },
        }

    def _get_fallback_insights(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback if AI call fails - still show basic metrics"""
        summary = portfolio_data.get("portfolio_summary", {})
        patterns = portfolio_data.get("trading_patterns", {})

        # Calculate basic metrics even if AI fails
        tech_concentration = 0
        if portfolio_data.get("sector_breakdown"):
            tech_sector = next(
                (
                    s
                    for s in portfolio_data["sector_breakdown"]
                    if s.get("sector") == "Technology"
                ),
                None,
            )
            if tech_sector:
                tech_concentration = tech_sector.get("percentage", 0)

        risk_level = (
            "High"
            if tech_concentration > 50
            else "Medium" if tech_concentration > 30 else "Low"
        )

        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "last_transaction_date": self._get_last_transaction_date(),
                "transactions_count": summary.get("total_transactions", 0),
                "positions_count": summary.get("total_positions", 0),
                "error": "ai_generation_failed",
            },
            "kpis": {
                "win_rate": round(patterns.get("win_rate", 0), 1),
                "market_avg_win_rate": 52,
                "avg_hold_days": round(patterns.get("avg_hold_days", 0)),
                "strategy_label": self._get_strategy_label(
                    patterns.get("avg_hold_days", 0)
                ),
                "positions_count": summary.get("total_positions", 0),
                "sector_concentration": round(tech_concentration, 1),
                "risk_level": risk_level,
                "risk_description": (
                    f"Sector concentration at {tech_concentration}%"
                    if tech_concentration > 30
                    else "Well diversified"
                ),
            },
            "ai_summary": {
                "quick_insight": "Unable to generate AI insights. Check API configuration. Showing basic metrics only."
            },
            "analysis": {
                "overall_assessment": "Unable to generate AI insights at this time. Please check your API configuration and try again. Basic portfolio metrics are displayed above.",
                "key_strengths": [],
                "key_risks": [],
                "behavioral_patterns": [],
                "recommendations": [],
            },
            "comparison": {
                "winners": {
                    "avg_return": round(patterns.get("avg_winner_return", 0), 1),
                    "hold_time": round(patterns.get("avg_winner_hold_days", 0)),
                    "success_rate": round(patterns.get("win_rate", 0), 1),
                },
                "losers": {
                    "avg_loss": round(patterns.get("avg_loser_return", 0), 1),
                    "hold_time": round(patterns.get("avg_loser_hold_days", 0)),
                    "pattern": "N/A",
                    "insight": None,
                },
            },
        }


# ================================================================
# Public API
# ================================================================


def get_portfolio_ai_insights(
    user_id: int, force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Get AI-powered portfolio insights.

    Args:
        user_id: User ID
        force_refresh: Skip cache

    Returns:
        AI analysis dict
    """
    analytics = PortfolioAIAnalytics(user_id)
    return analytics.get_insights(force_refresh=force_refresh)
