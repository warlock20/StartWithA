# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Transaction Service
Handles all business logic for creating, updating, and managing portfolio transactions.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from app import db
from app.models import (
    Transaction, PortfolioPosition, Company, DecisionJournal,
    ResearchProject, update_portfolio_position, ThesisEvolution
)
from app.services.currency_service import CurrencyService
from app.services.cash_service import CashService
from app.services.outcome_tracking import on_buy_transaction, on_sell_transaction
from app.services.intelligence_engine import IntelligenceEngine
from app.utils.time_utils import now_utc, parse_date_to_date_object

logger = logging.getLogger(__name__)


@dataclass
class TransactionValidationResult:
    """Result of transaction validation"""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class TransactionCreationResult:
    """Result of transaction creation"""
    success: bool
    transaction: Optional[Transaction] = None
    redirect_url: Optional[str] = None
    redirect_kwargs: dict = None
    message: Optional[str] = None
    error: Optional[str] = None
    warnings: List = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.redirect_kwargs is None:
            self.redirect_kwargs = {}


class TransactionService:
    """Service for handling portfolio transaction operations"""

    @staticmethod
    def validate_cash_transaction_data(
        transaction_type: str,
        date_str: str,
        cash_amount: str,
        fees: str = '0'
    ) -> TransactionValidationResult:
        """
        Validate DEPOSIT/WITHDRAWAL transaction data.
        """
        if not all([transaction_type, date_str, cash_amount]):
            return TransactionValidationResult(
                is_valid=False,
                error_message='Please fill in all required fields'
            )

        transaction_date = parse_date_to_date_object(date_str)
        if not transaction_date:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Invalid date format'
            )

        if transaction_date > now_utc().date():
            return TransactionValidationResult(
                is_valid=False,
                error_message='Transaction date cannot be in the future'
            )

        try:
            amount_decimal = Decimal(cash_amount)
        except (InvalidOperation, ValueError):
            return TransactionValidationResult(
                is_valid=False,
                error_message='Invalid amount'
            )

        if amount_decimal <= 0:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Amount must be greater than zero'
            )

        return TransactionValidationResult(is_valid=True)

    @staticmethod
    def validate_transaction_data(
        user_id: int,
        company_id: int,
        transaction_type: str,
        date_str: str,
        quantity: int,
        price_per_share: str,
        fees: str = '0'
    ) -> TransactionValidationResult:
        """
        Validate transaction input data.

        Returns:
            TransactionValidationResult with is_valid flag and error_message if invalid
        """
        # Check required fields
        if not all([company_id, transaction_type, date_str, quantity, price_per_share]):
            return TransactionValidationResult(
                is_valid=False,
                error_message='Please fill in all required fields'
            )

        # Validate company belongs to user
        company = Company.query.filter_by(id=company_id, user_id=user_id).first()
        if not company:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Invalid company selected'
            )

        # Parse and validate date
        transaction_date = parse_date_to_date_object(date_str)
        if not transaction_date:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Invalid date format'
            )

        # Validate date not in future
        if transaction_date > now_utc().date():
            return TransactionValidationResult(
                is_valid=False,
                error_message='Transaction date cannot be in the future'
            )

        # Parse numeric values
        try:
            price_decimal = Decimal(price_per_share)
            fees_decimal = Decimal(fees) if fees else Decimal('0.00')
        except (InvalidOperation, ValueError):
            return TransactionValidationResult(
                is_valid=False,
                error_message='Invalid price or fees amount'
            )

        # Validate quantity
        if quantity <= 0:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Quantity must be greater than zero'
            )

        # Validate price
        if price_decimal <= 0:
            return TransactionValidationResult(
                is_valid=False,
                error_message='Price per share must be greater than zero'
            )

        # Additional validation for SELL transactions
        if transaction_type == 'SELL':
            position = PortfolioPosition.query.filter_by(
                user_id=user_id,
                company_id=company_id
            ).first()

            if not position or position.total_shares < quantity:
                owned_shares = position.total_shares if position else 0
                return TransactionValidationResult(
                    is_valid=False,
                    error_message=f'Cannot sell {quantity} shares. You only own {owned_shares} shares of {company.ticker_symbol}'
                )

        # A dividend can only come from a company the user has held. The form
        # hides the others, but that is client-side only.
        if transaction_type == 'DIVIDEND':
            position = PortfolioPosition.query.filter_by(
                user_id=user_id,
                company_id=company_id
            ).first()

            if not position:
                return TransactionValidationResult(
                    is_valid=False,
                    error_message=f'Cannot record a dividend for {company.ticker_symbol}. You have never held shares in it'
                )

        return TransactionValidationResult(is_valid=True)

    @staticmethod
    def check_intelligence_warnings(
        user_id: int,
        company_id: int,
        transaction_type: str,
        quantity: int,
        price_per_share: Decimal
    ) -> List:
        """
        Check for intelligence engine warnings before transaction.

        Returns:
            List of Warning objects
        """
        warnings = []

        if transaction_type == 'BUY':
            try:
                amount = float(quantity) * float(price_per_share)
                engine = IntelligenceEngine(user_id)
                warnings = engine.check_buy_transaction(company_id, amount)
            except Exception as e:
                logger.warning(f"Failed to check intelligence warnings: {e}")

        return warnings

    @staticmethod
    def create_transaction(
        user_id: int,
        form_data: Dict,
        user_base_currency: str = 'USD'
    ) -> TransactionCreationResult:
        """
        Create a new transaction with full business logic.

        Args:
            user_id: User ID
            form_data: Form data dictionary from request.form
            user_base_currency: User's base currency

        Returns:
            TransactionCreationResult with success status and details
        """
        try:
            transaction_type = form_data.get('type')

            # === DEPOSIT / WITHDRAWAL ===
            if transaction_type in ('DEPOSIT', 'WITHDRAWAL'):
                return TransactionService._create_cash_transaction(
                    user_id=user_id,
                    form_data=form_data,
                    transaction_type=transaction_type,
                    user_base_currency=user_base_currency
                )

            # === BUY / SELL / DIVIDEND / SPLIT / SPINOFF ===
            # Extract form data
            company_id = int(form_data.get('company_id'))
            date_str = form_data.get('date')
            quantity = int(form_data.get('quantity'))
            price_per_share = form_data.get('price_per_share')
            fees = form_data.get('fees', '0')
            notes = form_data.get('notes', '').strip()
            currency = form_data.get('currency', 'USD').strip().upper()

            # Validate
            validation = TransactionService.validate_transaction_data(
                user_id=user_id,
                company_id=company_id,
                transaction_type=transaction_type,
                date_str=date_str,
                quantity=quantity,
                price_per_share=price_per_share,
                fees=fees
            )

            if not validation.is_valid:
                return TransactionCreationResult(
                    success=False,
                    error=validation.error_message
                )

            # Get company
            company = Company.query.filter_by(id=company_id, user_id=user_id).first()

            # Parse values
            transaction_date = parse_date_to_date_object(date_str)
            price_per_share_decimal = Decimal(price_per_share)
            fees_decimal = Decimal(fees) if fees else Decimal('0.00')

            # Check for intelligence warnings
            warnings = TransactionService.check_intelligence_warnings(
                user_id=user_id,
                company_id=company_id,
                transaction_type=transaction_type,
                quantity=quantity,
                price_per_share=price_per_share_decimal
            )

            # Currency conversion
            exchange_rate = CurrencyService.get_exchange_rate(
                from_currency=currency,
                to_currency=user_base_currency,
                rate_date=transaction_date
            )

            price_per_share_base = price_per_share_decimal * exchange_rate
            fees_base = fees_decimal * exchange_rate

            # Log currency conversion
            if currency != user_base_currency:
                logger.debug(f"Currency conversion: {currency} → {user_base_currency}")
                logger.debug(f"Exchange rate: {exchange_rate}")
                logger.debug(f"Price: {currency} {price_per_share_decimal} → {user_base_currency} {price_per_share_base}")

            # Handle BUY-specific logic
            bought_without_research = False
            is_add_to_position = False
            add_position_reason = None
            add_position_notes = None
            thesis_updated = False

            if transaction_type == 'BUY':
                # Check for existing position
                existing_position = PortfolioPosition.query.filter_by(
                    user_id=user_id,
                    company_id=company_id
                ).first()

                if existing_position and existing_position.total_shares > 0:
                    is_add_to_position = True
                    add_position_reason = form_data.get('add_position_reason')
                    add_position_notes = form_data.get('add_position_notes', '').strip()
                    thesis_updated = form_data.get('thesis_updated') == 'true'
                else:
                    # Check for research
                    research_project = ResearchProject.query.filter_by(
                        company_id=company_id,
                        user_id=user_id
                    ).first()

                    if not research_project:
                        bought_without_research = True

            # Create transaction
            transaction = Transaction(
                user_id=user_id,
                company_id=company_id,
                type=transaction_type,
                date=transaction_date,
                quantity=quantity,
                currency=currency,
                price_per_share=price_per_share_decimal,
                fees=fees_decimal,
                price_per_share_base=price_per_share_base,
                fees_base=fees_base,
                exchange_rate=exchange_rate,
                exchange_rate_date=transaction_date,
                notes=notes,
                bought_without_research=bought_without_research,
                is_add_to_position=is_add_to_position,
                add_position_reason=add_position_reason,
                add_position_notes=add_position_notes,
                thesis_updated=thesis_updated
            )

            db.session.add(transaction)
            db.session.flush()

            # Capture pre-sale cost basis for SELL
            pre_sale_cost_basis = None
            if transaction_type == 'SELL':
                position = PortfolioPosition.query.filter_by(
                    user_id=user_id,
                    company_id=company_id
                ).first()
                if position and position.average_cost_basis:
                    pre_sale_cost_basis = float(position.average_cost_basis)

            # Update portfolio position
            update_portfolio_position(transaction)

            # Create decision journal (handled separately for complexity)
            decision_journal = TransactionService._create_decision_journal(
                user_id=user_id,
                company_id=company_id,
                transaction=transaction,
                transaction_type=transaction_type,
                transaction_date=transaction_date,
                form_data=form_data,
                bought_without_research=bought_without_research,
                is_add_to_position=is_add_to_position
            )

            if decision_journal:
                transaction.decision_journal_id = decision_journal.id

            db.session.commit()

            # Update cash balance (may auto-create deposit if cash goes negative)
            cash_notice = CashService.update_after_transaction(user_id, transaction)
            if cash_notice:
                warnings.append(cash_notice)

            # AI Outcome tracking
            TransactionService._track_outcome(
                transaction=transaction,
                transaction_type=transaction_type,
                decision_journal=decision_journal,
                pre_sale_cost_basis=pre_sale_cost_basis,
                price_per_share=float(price_per_share_decimal),
                company=company
            )

            # Determine redirect
            redirect_url = 'portfolio.dashboard'
            redirect_kwargs = {}
            if transaction_type == 'SELL' and decision_journal:
                redirect_url = 'portfolio.sell_postmortem'
                redirect_kwargs = {'journal_id': decision_journal.id}

            return TransactionCreationResult(
                success=True,
                transaction=transaction,
                redirect_url=redirect_url,
                redirect_kwargs=redirect_kwargs,
                message=f'{transaction_type} transaction for {company.ticker_symbol} recorded successfully',
                warnings=warnings
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating transaction: {e}", exc_info=True)
            return TransactionCreationResult(
                success=False,
                error=f'Error adding transaction: {str(e)}'
            )

    @staticmethod
    def _create_cash_transaction(
        user_id: int,
        form_data: Dict,
        transaction_type: str,
        user_base_currency: str = 'USD'
    ) -> TransactionCreationResult:
        """Create a DEPOSIT or WITHDRAWAL transaction."""
        date_str = form_data.get('date')
        cash_amount_str = form_data.get('cash_amount', '0')
        fees = form_data.get('fees', '0')
        notes = form_data.get('notes', '').strip()
        currency = form_data.get('currency', 'USD').strip().upper()

        # Validate
        validation = TransactionService.validate_cash_transaction_data(
            transaction_type=transaction_type,
            date_str=date_str,
            cash_amount=cash_amount_str,
            fees=fees
        )

        if not validation.is_valid:
            return TransactionCreationResult(
                success=False,
                error=validation.error_message
            )

        transaction_date = parse_date_to_date_object(date_str)
        cash_amount = Decimal(cash_amount_str)
        fees_decimal = Decimal(fees) if fees else Decimal('0.00')

        # Currency conversion for cash amount
        exchange_rate = CurrencyService.get_exchange_rate(
            from_currency=currency,
            to_currency=user_base_currency,
            rate_date=transaction_date
        )

        cash_amount_base = cash_amount * exchange_rate
        fees_base = fees_decimal * exchange_rate

        transaction = Transaction(
            user_id=user_id,
            type=transaction_type,
            date=transaction_date,
            currency=currency,
            cash_amount=cash_amount,
            cash_amount_base=cash_amount_base,
            fees=fees_decimal,
            fees_base=fees_base,
            exchange_rate=exchange_rate,
            exchange_rate_date=transaction_date,
            notes=notes
        )

        db.session.add(transaction)
        db.session.commit()

        # Update cash balance
        CashService.update_after_transaction(user_id, transaction)

        label = 'Deposit' if transaction_type == 'DEPOSIT' else 'Withdrawal'
        return TransactionCreationResult(
            success=True,
            transaction=transaction,
            redirect_url='portfolio.dashboard',
            message=f'{label} of {currency} {cash_amount:,.2f} recorded successfully'
        )

    @staticmethod
    def _create_decision_journal(
        user_id: int,
        company_id: int,
        transaction: Transaction,
        transaction_type: str,
        transaction_date,
        form_data: Dict,
        bought_without_research: bool,
        is_add_to_position: bool
    ) -> Optional[DecisionJournal]:
        """Create decision journal entry for transaction"""

        if transaction_type == 'BUY':
            existing_journal = DecisionJournal.query.filter_by(
                company_id=company_id,
                user_id=user_id,
                decision_type='BUY',
                is_portfolio_decision=True
            ).first()

            if existing_journal and is_add_to_position:
                return existing_journal
            elif not existing_journal:
                if bought_without_research:
                    investment_thesis = form_data.get('investment_thesis', '').strip()
                    word_count = len(investment_thesis.split())
                    thesis_depth = 'comprehensive' if word_count > 100 else ('brief' if word_count >= 50 else 'minimal')

                    journal = DecisionJournal(
                        user_id=user_id,
                        company_id=company_id,
                        decision_type='BUY',
                        decision_date=transaction_date,
                        investment_thesis=investment_thesis,
                        confidence_score=form_data.get('confidence_score', type=int),
                        expected_return=form_data.get('expected_return', type=float),
                        expected_timeframe=form_data.get('expected_timeframe', type=int),
                        is_portfolio_decision=True,
                        thesis_depth=thesis_depth,
                        thesis_word_count=word_count,
                        non_research_source=form_data.get('non_research_source', '').strip()
                    )

                    # Create ThesisEvolution Version 0 for non-research purchases
                    # Check if version 0 already exists for this company
                    existing_v0 = ThesisEvolution.query.filter_by(
                        user_id=user_id,
                        company_id=company_id,
                        version=0
                    ).first()

                    if not existing_v0 and investment_thesis:
                        thesis_evolution = ThesisEvolution(
                            user_id=user_id,
                            company_id=company_id,
                            version=0,
                            thesis=investment_thesis,
                            change_summary='Initial investment thesis from direct purchase',
                            change_trigger=f'Buy transaction without research ({form_data.get("non_research_source", "unknown")})',
                            conviction_level=form_data.get('confidence_score', type=int),  # Set from transaction form
                            is_current=True,
                            created_at=transaction_date or now_utc()
                        )
                        db.session.add(thesis_evolution)
                        logger.info(f"Created ThesisEvolution v0 for company {company_id} from non-research purchase")

                else:
                    research_project = ResearchProject.query.filter_by(
                        company_id=company_id,
                        user_id=user_id
                    ).first()

                    if research_project:
                        journal = DecisionJournal(
                            user_id=user_id,
                            company_id=company_id,
                            decision_type='BUY',
                            decision_date=transaction_date,
                            investment_thesis=research_project.investment_thesis or 'Investment thesis from research',
                            confidence_score=form_data.get('confidence_score', type=int),
                            expected_return=form_data.get('expected_return', type=float),
                            expected_timeframe=form_data.get('expected_timeframe', type=int),
                            is_portfolio_decision=True,
                            linked_research_id=research_project.id,
                            thesis_depth='comprehensive'
                        )
                    else:
                        return None

                db.session.add(journal)
                db.session.flush()
                return journal

        elif transaction_type == 'SELL':
            sell_journal = DecisionJournal(
                user_id=user_id,
                company_id=company_id,
                decision_type='SELL',
                decision_date=transaction_date,
                investment_thesis=f'Selling {transaction.quantity} shares at ${transaction.price_per_share}',
                is_portfolio_decision=True
            )
            db.session.add(sell_journal)
            db.session.flush()
            return sell_journal

        return None

    @staticmethod
    def _track_outcome(
        transaction: Transaction,
        transaction_type: str,
        decision_journal: Optional[DecisionJournal],
        pre_sale_cost_basis: Optional[float],
        price_per_share: float,
        company: Company
    ):
        """Track outcome for AI learning"""

        if transaction_type == 'BUY':
            try:
                outcome = on_buy_transaction(
                    transaction=transaction,
                    decision_journal=decision_journal
                )
                if outcome:
                    logger.info(f"[AI] Created ResearchOutcome {outcome.id} for {company.ticker_symbol} "
                               f"(quality_score={outcome.research_quality_score})")
            except Exception as e:
                logger.warning(f"[AI] Failed to create outcome record: {e}")

        elif transaction_type == 'SELL' and pre_sale_cost_basis:
            try:
                realized_return_pct = ((price_per_share - pre_sale_cost_basis) / pre_sale_cost_basis) * 100

                outcome = on_sell_transaction(
                    transaction=transaction,
                    realized_return_pct=realized_return_pct
                )
                if outcome:
                    logger.info(f"[AI] Updated ResearchOutcome {outcome.id}: "
                               f"{outcome.outcome_category} ({realized_return_pct:.1f}%)")
            except Exception as e:
                logger.warning(f"[AI] Failed to update outcome record: {e}")
