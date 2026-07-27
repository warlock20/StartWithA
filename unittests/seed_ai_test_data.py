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
AI Test Data Generator
======================

Generates realistic test data for AI features:
- Intelligence Engine (concentration warnings, behavioral patterns)
- Thesis Analysis (quality scoring)
- Similar Mistakes (embedding similarity)
- Research Quality (correlation with outcomes)
- Configuration System (user profiles)

Usage:
    python -m tests.seed_ai_test_data
    python -m tests.seed_ai_test_data --clean  # Wipe AI-related data first
    python -m tests.seed_ai_test_data --users 20 --transactions 50

Author: Generated for StartWithA
"""

import argparse
import random
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from faker import Faker
from werkzeug.security import generate_password_hash

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User
from app.models.company import Company
from app.models.portfolio import Transaction, PortfolioPosition, update_portfolio_position
from app.models.journal import DecisionJournal
from app.models.research import ResearchProject, WorkSession, ChecklistAnswer
from app.models.checklist import DestinationCheckpoint
from app.models.configuration import UserInvestmentProfile, InvestorProfile
from app.models.idea_pipeline import MistakeLog

# Initialize Faker
fake = Faker()
Faker.seed(42)  # Reproducibility
random.seed(42)


# ============================================
# CONFIGURATION (All tunables here)
# ============================================

CONFIG = {
    # Scale
    'user_count': 15,
    'transactions_per_user': (20, 50),  # (min, max)
    'companies_count': 100,
    
    # Time
    'history_days': 730,  # 2 years
    
    # Persona distribution (should sum to 1.0)
    'personas': {
        'emotional_trader': 0.25,
        'overconfident_expert': 0.20,
        'disciplined_investor': 0.20,  # Clean user
        'impatient_beginner': 0.20,
        'gambler': 0.15,
    },
    
    # Patterns to generate
    'patterns_enabled': {
        'averaging_down': True,
        'selling_winners_early': True,
        'holding_losers': True,
        'overconfidence': True,
    },
    
    # Research quality ranges by persona (0-100)
    'research_quality': {
        'emotional_trader': (20, 50),
        'overconfident_expert': (40, 70),
        'disciplined_investor': (70, 95),
        'impatient_beginner': (15, 40),
        'gambler': (5, 30),
    },
    
    # Confidence ranges by persona (1-10)
    'confidence_levels': {
        'emotional_trader': (5, 8),
        'overconfident_expert': (8, 10),
        'disciplined_investor': (5, 7),
        'impatient_beginner': (4, 7),
        'gambler': (7, 10),
    },
}


# ============================================
# TEMPLATES
# ============================================

SECTORS = [
    {'id': 1, 'name': 'Technology', 'industries': ['Software', 'Hardware', 'Semiconductors', 'Cloud Computing']},
    {'id': 2, 'name': 'Healthcare', 'industries': ['Pharmaceuticals', 'Biotech', 'Medical Devices', 'Healthcare Services']},
    {'id': 3, 'name': 'Financials', 'industries': ['Banks', 'Insurance', 'Asset Management', 'Fintech']},
    {'id': 4, 'name': 'Consumer Discretionary', 'industries': ['Retail', 'Automotive', 'Restaurants', 'E-commerce']},
    {'id': 5, 'name': 'Consumer Staples', 'industries': ['Food & Beverage', 'Household Products', 'Tobacco']},
    {'id': 6, 'name': 'Energy', 'industries': ['Oil & Gas', 'Renewables', 'Utilities']},
    {'id': 7, 'name': 'Industrials', 'industries': ['Aerospace', 'Manufacturing', 'Transportation', 'Construction']},
    {'id': 8, 'name': 'Materials', 'industries': ['Chemicals', 'Mining', 'Steel', 'Packaging']},
    {'id': 9, 'name': 'Real Estate', 'industries': ['REITs', 'Property Development', 'Property Management']},
    {'id': 10, 'name': 'Communication Services', 'industries': ['Telecom', 'Media', 'Entertainment', 'Social Media']},
]

# Strong thesis templates (for disciplined investors)
STRONG_THESIS_TEMPLATES = [
    "I believe {company} is undervalued due to {reason}. The market is pricing in {negative}, but my research shows {positive}. Key catalyst: {catalyst}. I expect {upside}% upside over {timeframe} months.",
    "{company} has a durable competitive moat from {moat}. Current P/E of {pe}x vs industry average of {industry_pe}x represents a {discount}% discount. Management has {track_record}. My price target is ${target}.",
    "Investing in {company} based on: 1) {reason1}, 2) {reason2}, 3) {reason3}. Main risks: {risk1}, {risk2}. Position sizing: {position}% of portfolio given risk/reward profile.",
    "{company} is a classic {style} play. {metric} has grown {growth}% annually for {years} years. Balance sheet is {balance_sheet} with {debt_situation}. Insider buying of ${insider}M in last 6 months signals confidence.",
]

# Weak thesis templates (for emotional/beginner investors)
WEAK_THESIS_TEMPLATES = [
    "Stock looks cheap. Buying.",
    "{company} is going up. Don't want to miss out.",
    "Heard about {company} on Twitter. Seems interesting. YOLO.",
    "Everyone's talking about {company}. Must be good.",
    "{company} is down a lot, has to bounce back.",
    "My friend made money on {company}. Getting in.",
]

# Medium thesis templates
MEDIUM_THESIS_TEMPLATES = [
    "{company} looks undervalued at current levels. P/E is below average. Could see upside.",
    "Buying {company} for growth potential. New product launch coming. Some risk but worth it.",
    "{company} has good fundamentals. Revenue growing. Management seems competent.",
]

# Mistake patterns (semantic similarity groups)
MISTAKE_PATTERNS = {
    'fomo': [
        {"title": "Bought into the hype", "description": "Purchased {company} after a 40% run-up. Got caught up in social media buzz and FOMO. Didn't do proper due diligence. Stock dropped 25% after I bought."},
        {"title": "Chased the momentum", "description": "Jumped into {company} because everyone was talking about it. Ignored valuation, ignored my process. Classic fear of missing out."},
        {"title": "Social media influenced decision", "description": "Twitter was going crazy about {company}. Bought without research. Hype-driven purchase that I regret."},
    ],
    'ignored_debt': [
        {"title": "Ignored balance sheet risk", "description": "Focused only on revenue growth at {company}, completely missed the deteriorating debt situation. Debt to equity was 3x when I should have walked away."},
        {"title": "Overlooked leverage", "description": "{company} had too much debt. I saw the growth story and ignored the liabilities. When rates rose, stock collapsed."},
        {"title": "Missed the debt warning signs", "description": "Should have seen the debt load at {company} was unsustainable. Was blinded by the growth narrative."},
    ],
    'overconfidence': [
        {"title": "Too confident in my analysis", "description": "Was certain {company} would hit my target. Sized position too large. Ignored contrary evidence. Ego got in the way."},
        {"title": "Dismissed warning signs", "description": "Multiple red flags at {company} but I was sure I was right. Confirmation bias at its worst."},
        {"title": "Ignored the bear case", "description": "Didn't stress test my {company} thesis. Was overconfident. Should have considered what could go wrong."},
    ],
    'no_research': [
        {"title": "Bought without research", "description": "Purchased {company} on a whim. No checklist, no analysis, no process. Just gambling disguised as investing."},
        {"title": "Skipped due diligence", "description": "Was lazy with {company}. Didn't read the 10-K, didn't analyze competitors. Paid the price."},
        {"title": "Impulse buy", "description": "{company} was an impulse decision. No thesis, no exit plan. Amateur mistake."},
    ],
    'averaging_down_mistake': [
        {"title": "Averaged down into disaster", "description": "Kept buying {company} as it fell. First buy at $50, then $40, then $30. Now it's at $15. Threw good money after bad."},
        {"title": "Catching falling knife", "description": "Thought {company} was cheap at -20%. Then -40%. Then -60%. Kept adding. Should have cut losses."},
        {"title": "Refused to admit I was wrong", "description": "Every dip in {company} I bought more. Ego wouldn't let me sell. Classic averaging down trap."},
    ],
}

# Checkpoint templates
CHECKPOINT_TEMPLATES = [
    {"description": "Q{quarter} earnings: Revenue > ${revenue}M", "timeframe_days": 90},
    {"description": "New product launch by {date}", "timeframe_days": 180},
    {"description": "Market share above {share}%", "timeframe_days": 365},
    {"description": "Debt/Equity ratio below {ratio}", "timeframe_days": 180},
    {"description": "Management delivers on {initiative}", "timeframe_days": 270},
    {"description": "Gross margin expansion to {margin}%", "timeframe_days": 180},
]


# ============================================
# PERSONA DEFINITIONS
# ============================================

class Persona:
    """Base class for investor personas."""
    
    name: str = "base"
    profile_type: str = "intermediate"  # Maps to InvestorProfile
    
    # Pattern probabilities (0-1)
    averaging_down_prob: float = 0.0
    selling_early_prob: float = 0.0
    holding_losers_prob: float = 0.0
    overconfidence_prob: float = 0.0
    
    # Behavior
    research_before_buy_prob: float = 0.5  # Probability of having research
    checkpoint_creation_prob: float = 0.5
    journal_completion_prob: float = 0.5
    
    def get_thesis_template(self) -> str:
        return random.choice(MEDIUM_THESIS_TEMPLATES)
    
    def get_confidence(self) -> int:
        return random.randint(*CONFIG['confidence_levels'].get(self.name, (5, 7)))
    
    def get_research_quality(self) -> int:
        return random.randint(*CONFIG['research_quality'].get(self.name, (40, 60)))


class EmotionalTrader(Persona):
    name = "emotional_trader"
    profile_type = "beginner"
    
    averaging_down_prob = 0.6
    selling_early_prob = 0.5
    holding_losers_prob = 0.7
    overconfidence_prob = 0.4
    
    research_before_buy_prob = 0.3
    checkpoint_creation_prob = 0.2
    journal_completion_prob = 0.4
    
    def get_thesis_template(self) -> str:
        if random.random() < 0.7:
            return random.choice(WEAK_THESIS_TEMPLATES)
        return random.choice(MEDIUM_THESIS_TEMPLATES)


class OverconfidentExpert(Persona):
    name = "overconfident_expert"
    profile_type = "expert"
    
    averaging_down_prob = 0.4
    selling_early_prob = 0.2
    holding_losers_prob = 0.6
    overconfidence_prob = 0.9  # Very high
    
    research_before_buy_prob = 0.7
    checkpoint_creation_prob = 0.5
    journal_completion_prob = 0.7
    
    def get_thesis_template(self) -> str:
        if random.random() < 0.5:
            return random.choice(STRONG_THESIS_TEMPLATES)
        return random.choice(MEDIUM_THESIS_TEMPLATES)


class DisciplinedInvestor(Persona):
    """Clean user - minimal bad patterns."""
    name = "disciplined_investor"
    profile_type = "expert"
    
    averaging_down_prob = 0.1  # Rarely
    selling_early_prob = 0.1
    holding_losers_prob = 0.1
    overconfidence_prob = 0.1
    
    research_before_buy_prob = 0.95
    checkpoint_creation_prob = 0.8
    journal_completion_prob = 0.9
    
    def get_thesis_template(self) -> str:
        return random.choice(STRONG_THESIS_TEMPLATES)


class ImpatientBeginner(Persona):
    name = "impatient_beginner"
    profile_type = "beginner"
    
    averaging_down_prob = 0.3
    selling_early_prob = 0.8  # Very impatient
    holding_losers_prob = 0.3
    overconfidence_prob = 0.3
    
    research_before_buy_prob = 0.2
    checkpoint_creation_prob = 0.1
    journal_completion_prob = 0.3
    
    def get_thesis_template(self) -> str:
        return random.choice(WEAK_THESIS_TEMPLATES)


class Gambler(Persona):
    name = "gambler"
    profile_type = "beginner"
    
    averaging_down_prob = 0.8  # Doubles down constantly
    selling_early_prob = 0.4
    holding_losers_prob = 0.5
    overconfidence_prob = 0.7
    
    research_before_buy_prob = 0.1
    checkpoint_creation_prob = 0.05
    journal_completion_prob = 0.2
    
    def get_thesis_template(self) -> str:
        return random.choice(WEAK_THESIS_TEMPLATES)


PERSONA_CLASSES = {
    'emotional_trader': EmotionalTrader,
    'overconfident_expert': OverconfidentExpert,
    'disciplined_investor': DisciplinedInvestor,
    'impatient_beginner': ImpatientBeginner,
    'gambler': Gambler,
}


# ============================================
# DATA GENERATORS
# ============================================

class AITestDataGenerator:
    """Main generator class."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.users: List[User] = []
        self.companies: List[Company] = []
        self.transactions: List[Transaction] = []
        self.journals: List[DecisionJournal] = []
        self.stats = {
            'users_created': 0,
            'companies_created': 0,
            'transactions_created': 0,
            'patterns': {
                'averaging_down': 0,
                'selling_early': 0,
                'holding_losers': 0,
                'overconfidence': 0,
            },
            'research_projects': 0,
            'mistakes': 0,
        }
    
    def run(self, clean: bool = False):
        """Main entry point."""
        self._print_config()
        
        if clean:
            self._clean_data()
        
        self._create_users_with_personas()
        self._create_companies()
        self._create_transactions_and_patterns()
        self._create_research_and_quality()
        self._create_mistakes()
        self._link_user_profiles()
        
        self._print_summary()
    
    def _print_config(self):
        """Print configuration."""
        print("\n" + "="*60)
        print("📊 AI TEST DATA GENERATOR")
        print("="*60)
        print(f"\n⚙️  Configuration:")
        print(f"   Users: {self.config['user_count']}")
        print(f"   Companies: {self.config['companies_count']}")
        print(f"   Transactions per user: {self.config['transactions_per_user']}")
        print(f"   History: {self.config['history_days']} days ({self.config['history_days']//365} years)")
        print(f"\n   Persona Distribution:")
        for persona, pct in self.config['personas'].items():
            count = int(self.config['user_count'] * pct)
            clean = " (clean)" if persona == 'disciplined_investor' else ""
            print(f"      {persona}: {count} users{clean}")
        print()
    
    def _clean_data(self):
        """Clean AI-related data (preserves core data)."""
        print("🧹 Cleaning AI test data...")

        # Delete in order of dependencies (most dependent first)
        try:
            # Import JournalEntry and ResearchMetrics
            from app.models.journal import JournalEntry
            from app.models.research import ResearchMetrics

            # Delete most dependent tables first (in reverse dependency order)
            db.session.query(DestinationCheckpoint).delete()
            db.session.query(ChecklistAnswer).delete()
            db.session.query(WorkSession).delete()
            db.session.query(JournalEntry).delete()  # Must come before ResearchProject
            db.session.query(ResearchProject).delete()
            db.session.query(ResearchMetrics).delete()  # Must come before User
            db.session.query(MistakeLog).delete()
            db.session.query(Transaction).delete()  # Must come before DecisionJournal and Company
            db.session.query(DecisionJournal).delete()
            db.session.query(PortfolioPosition).delete()
            db.session.query(UserInvestmentProfile).delete()

            # Delete test companies BEFORE users (companies reference users)
            db.session.query(Company).filter(
                Company.ticker_symbol.like('TEST%')
            ).delete(synchronize_session=False)

            # Delete test users last (many tables reference users)
            db.session.query(User).filter(
                User.email.like('%@testpersona.ai')
            ).delete(synchronize_session=False)

            db.session.commit()
            print("   ✨ Cleaned.")
        except Exception as e:
            db.session.rollback()
            print(f"   ⚠️  Error during cleanup: {e}")
            print(f"   💡 Continuing anyway...")
    
    def _create_companies(self):
        """Create test companies."""
        print(f"🏢 Creating {self.config['companies_count']} companies...")
        
        used_tickers = set()
        
        for i in range(self.config['companies_count']):
            # Generate unique ticker
            while True:
                ticker = f"TEST{fake.lexify(text='???').upper()}"
                if ticker not in used_tickers:
                    used_tickers.add(ticker)
                    break
            
            sector = random.choice(SECTORS)
            
            company = Company(
                name=fake.company(),
                ticker_symbol=ticker,
                sector_id=sector['id'],
                industry=random.choice(sector['industries']),
                summary=fake.catch_phrase(),
                user_id=random.choice(self.users).id,
            )
            
            db.session.add(company)
            self.companies.append(company)
        
        db.session.commit()
        self.stats['companies_created'] = len(self.companies)
        print(f"   ✅ Created {len(self.companies)} companies")
    
    def _create_users_with_personas(self):
        """Create users with assigned personas."""
        print(f"\n👤 Creating {self.config['user_count']} users with personas...")
        
        # Calculate users per persona
        user_assignments = []
        for persona_name, ratio in self.config['personas'].items():
            count = int(self.config['user_count'] * ratio)
            user_assignments.extend([persona_name] * count)
        
        # Fill remaining slots
        while len(user_assignments) < self.config['user_count']:
            user_assignments.append(random.choice(list(self.config['personas'].keys())))
        
        random.shuffle(user_assignments)
        
        for i, persona_name in enumerate(user_assignments):
            persona_class = PERSONA_CLASSES[persona_name]
            persona = persona_class()
            
            user = User(
                username=f"{persona_name}_{i}",
                email=f"{persona_name}_{i}@testpersona.ai",
                password_hash=generate_password_hash("test123"),
                onboarding_completed=True,
            )
            
            # Store persona as attribute for later use
            user._persona = persona
            user._persona_name = persona_name
            
            db.session.add(user)
            self.users.append(user)
        
        db.session.commit()
        self.stats['users_created'] = len(self.users)
        
        # Print distribution
        persona_counts = {}
        for user in self.users:
            persona_counts[user._persona_name] = persona_counts.get(user._persona_name, 0) + 1
        
        for persona, count in persona_counts.items():
            print(f"   ├── {count}x {persona}")
        print(f"   └── Total: {len(self.users)} users")
    
    def _create_transactions_and_patterns(self):
        """Create transactions with behavioral patterns."""
        print(f"\n💰 Generating transactions with patterns...")
        
        history_start = datetime.now() - timedelta(days=self.config['history_days'])
        
        for user in self.users:
            persona = user._persona
            num_transactions = random.randint(*self.config['transactions_per_user'])
            
            user_patterns = {'averaging_down': 0, 'selling_early': 0, 'holding_losers': 0, 'overconfidence': 0}
            
            # Select companies for this user
            user_companies = random.sample(self.companies, min(20, len(self.companies)))
            
            # Track positions for pattern generation
            positions = {}  # company_id -> list of buys
            
            for _ in range(num_transactions):
                company = random.choice(user_companies)
                tx_date = fake.date_time_between(start_date=history_start, end_date='now')
                
                # Decide transaction type and pattern
                pattern_type = self._decide_pattern(persona, company.id, positions)
                
                if pattern_type == 'averaging_down' and company.id in positions:
                    # Buy more at lower price
                    tx = self._create_averaging_down_transaction(user, company, positions, tx_date)
                    user_patterns['averaging_down'] += 1
                    self.stats['patterns']['averaging_down'] += 1
                    
                elif pattern_type == 'selling_early' and company.id in positions:
                    # Sell at modest gain
                    tx = self._create_selling_early_transaction(user, company, positions, tx_date)
                    user_patterns['selling_early'] += 1
                    self.stats['patterns']['selling_early'] += 1
                    
                elif pattern_type == 'holding_loser' and company.id not in positions:
                    # Buy something that will be held at a loss
                    tx = self._create_holding_loser_transaction(user, company, positions, tx_date)
                    user_patterns['holding_losers'] += 1
                    self.stats['patterns']['holding_losers'] += 1
                    
                else:
                    # Normal transaction
                    tx = self._create_normal_transaction(user, company, positions, tx_date)
                
                if tx:
                    db.session.add(tx)
                    db.session.flush()  # Get transaction ID
                    self.transactions.append(tx)

                    # Update portfolio position
                    update_portfolio_position(tx)

                    # Create decision journal for BUY transactions
                    if tx.type == 'BUY':
                        journal = self._create_decision_journal(user, company, tx, persona)
                        if journal:
                            db.session.add(journal)
                            self.journals.append(journal)
                            
                            # Track overconfidence
                            if persona.overconfidence_prob > random.random():
                                user_patterns['overconfidence'] += 1
                                self.stats['patterns']['overconfidence'] += 1
            
            # Commit per user to avoid huge transaction
            db.session.commit()
        
        self.stats['transactions_created'] = len(self.transactions)
        print(f"   ✅ Created {len(self.transactions)} transactions")
        print(f"   📈 Patterns: averaging_down({self.stats['patterns']['averaging_down']}), "
              f"selling_early({self.stats['patterns']['selling_early']}), "
              f"holding_losers({self.stats['patterns']['holding_losers']}), "
              f"overconfidence({self.stats['patterns']['overconfidence']})")
    
    def _decide_pattern(self, persona: Persona, company_id: int, positions: Dict) -> Optional[str]:
        """Decide which pattern to apply based on persona probabilities."""
        if not self.config['patterns_enabled']:
            return None
        
        if self.config['patterns_enabled'].get('averaging_down') and \
           company_id in positions and \
           random.random() < persona.averaging_down_prob:
            return 'averaging_down'
        
        if self.config['patterns_enabled'].get('selling_winners_early') and \
           company_id in positions and \
           random.random() < persona.selling_early_prob:
            return 'selling_early'
        
        if self.config['patterns_enabled'].get('holding_losers') and \
           company_id not in positions and \
           random.random() < persona.holding_losers_prob:
            return 'holding_loser'
        
        return None
    
    def _create_averaging_down_transaction(self, user: User, company: Company, 
                                           positions: Dict, tx_date: datetime) -> Transaction:
        """Create a BUY at lower price than previous."""
        prev_buys = positions.get(company.id, [])
        if prev_buys:
            last_price = prev_buys[-1]['price']
            # Buy at 10-30% lower
            new_price = last_price * random.uniform(0.7, 0.9)
        else:
            new_price = random.uniform(20, 200)
        
        quantity = random.randint(10, 100)
        
        tx = Transaction(
            user_id=user.id,
            company_id=company.id,
            type='BUY',
            quantity=quantity,
            price_per_share=round(new_price, 2),
            date=tx_date,
        )
        
        # Track position
        if company.id not in positions:
            positions[company.id] = []
        positions[company.id].append({'price': new_price, 'quantity': quantity, 'date': tx_date})
        
        return tx
    
    def _create_selling_early_transaction(self, user: User, company: Company,
                                          positions: Dict, tx_date: datetime) -> Transaction:
        """Create a SELL at modest gain after short holding period."""
        prev_buys = positions.get(company.id, [])
        if not prev_buys:
            return None
        
        avg_price = sum(b['price'] for b in prev_buys) / len(prev_buys)
        total_shares = sum(b['quantity'] for b in prev_buys)
        
        # Sell at 5-15% gain (leaving money on table)
        sell_price = avg_price * random.uniform(1.05, 1.15)
        
        tx = Transaction(
            user_id=user.id,
            company_id=company.id,
            type='SELL',
            quantity=total_shares,
            price_per_share=round(sell_price, 2),
            date=tx_date,
        )
        
        # Clear position
        del positions[company.id]
        
        return tx
    
    def _create_holding_loser_transaction(self, user: User, company: Company,
                                          positions: Dict, tx_date: datetime) -> Transaction:
        """Create a BUY that will be held at a loss (no corresponding sell)."""
        # Buy at a "high" price - represents bad timing
        price = random.uniform(50, 300)
        quantity = random.randint(20, 100)
        
        tx = Transaction(
            user_id=user.id,
            company_id=company.id,
            type='BUY',
            quantity=quantity,
            price_per_share=round(price, 2),
            date=tx_date,
        )
        
        # Track position (will not be sold)
        positions[company.id] = [{'price': price, 'quantity': quantity, 'date': tx_date}]
        
        return tx
    
    def _create_normal_transaction(self, user: User, company: Company,
                                   positions: Dict, tx_date: datetime) -> Transaction:
        """Create a normal BUY or SELL transaction."""
        if company.id in positions and random.random() < 0.3:
            # Sell
            prev_buys = positions[company.id]
            total_shares = sum(b['quantity'] for b in prev_buys)
            avg_price = sum(b['price'] for b in prev_buys) / len(prev_buys)
            
            # Random outcome
            price_change = random.uniform(0.7, 1.5)
            sell_price = avg_price * price_change
            
            tx = Transaction(
                user_id=user.id,
                company_id=company.id,
                type='SELL',
                quantity=total_shares,
                price_per_share=round(sell_price, 2),
                date=tx_date,
            )
            
            del positions[company.id]
        else:
            # Buy
            price = random.uniform(20, 300)
            quantity = random.randint(10, 100)
            
            tx = Transaction(
                user_id=user.id,
                company_id=company.id,
                type='BUY',
                quantity=quantity,
                price_per_share=round(price, 2),
                date=tx_date,
            )
            
            if company.id not in positions:
                positions[company.id] = []
            positions[company.id].append({'price': price, 'quantity': quantity, 'date': tx_date})
        
        return tx
    
    def _create_decision_journal(self, user: User, company: Company, 
                                 tx: Transaction, persona: Persona) -> Optional[DecisionJournal]:
        """Create decision journal with thesis based on persona."""
        if random.random() > persona.journal_completion_prob:
            return None
        
        template = persona.get_thesis_template()
        thesis = self._fill_thesis_template(template, company)
        confidence = persona.get_confidence()
        
        journal = DecisionJournal(
            user_id=user.id,
            company_id=company.id,
            decision_type='invest',
            decision_date=tx.date,
            investment_thesis=thesis,
            confidence_score=confidence,
            is_portfolio_decision=True,
            created_at=tx.date,
        )
        
        # Create checkpoints for disciplined investors
        if random.random() < persona.checkpoint_creation_prob:
            self._create_checkpoints_for_journal(journal, company)
        
        return journal
    
    def _fill_thesis_template(self, template: str, company: Company) -> str:
        """Fill in thesis template with realistic values."""
        replacements = {
            '{company}': company.name,
            '{reason}': random.choice(['temporary headwinds', 'market overreaction', 'hidden assets', 'cyclical low']),
            '{negative}': random.choice(['slowing growth', 'margin compression', 'competitive threats']),
            '{positive}': random.choice(['improving fundamentals', 'market share gains', 'new product traction']),
            '{catalyst}': random.choice(['earnings beat', 'new CEO', 'activist involvement', 'sector rotation']),
            '{upside}': str(random.randint(20, 100)),
            '{timeframe}': str(random.randint(6, 24)),
            '{moat}': random.choice(['network effects', 'brand strength', 'switching costs', 'scale advantages']),
            '{pe}': str(random.randint(8, 20)),
            '{industry_pe}': str(random.randint(15, 30)),
            '{discount}': str(random.randint(20, 50)),
            '{track_record}': random.choice(['delivered 15% ROIC', 'grown EPS 20% annually', 'excellent capital allocation']),
            '{target}': str(random.randint(50, 500)),
            '{reason1}': random.choice(['strong moat', 'pricing power', 'recurring revenue']),
            '{reason2}': random.choice(['management alignment', 'insider buying', 'capital discipline']),
            '{reason3}': random.choice(['reasonable valuation', 'margin of safety', 'asymmetric upside']),
            '{risk1}': random.choice(['competition', 'regulation', 'execution']),
            '{risk2}': random.choice(['macro headwinds', 'key man risk', 'customer concentration']),
            '{position}': str(random.randint(2, 10)),
            '{style}': random.choice(['value', 'growth', 'GARP', 'turnaround']),
            '{metric}': random.choice(['Revenue', 'EBITDA', 'FCF', 'EPS']),
            '{growth}': str(random.randint(10, 30)),
            '{years}': str(random.randint(3, 10)),
            '{balance_sheet}': random.choice(['fortress', 'solid', 'adequate']),
            '{debt_situation}': random.choice(['net cash position', 'low leverage', 'manageable debt']),
            '{insider}': str(round(random.uniform(0.5, 5), 1)),
        }
        
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    def _create_checkpoints_for_journal(self, journal: DecisionJournal, company: Company):
        """Create destination checkpoints."""
        num_checkpoints = random.randint(1, 3)
        templates = random.sample(CHECKPOINT_TEMPLATES, num_checkpoints)
        
        for tmpl in templates:
            target_date = datetime.now() + timedelta(days=tmpl['timeframe_days'])
            
            description = tmpl['description'].format(
                quarter=random.randint(1, 4),
                revenue=random.randint(100, 1000),
                date=target_date.strftime('%B %Y'),
                share=random.randint(10, 40),
                ratio=round(random.uniform(0.5, 2.0), 1),
                initiative=random.choice(['cost cutting', 'expansion', 'product launch']),
                margin=random.randint(30, 60),
            )
            
            # Random status
            if target_date < datetime.now():
                status = random.choice(['met', 'not_met', 'partially_met'])
            else:
                status = 'pending'
            
            checkpoint = DestinationCheckpoint(
                company_id=company.id,
                user_id=journal.user_id,
                metric=description,
                expectation=f"Target: {description}",
                target_date=target_date,
                status=status,
            )
            db.session.add(checkpoint)
    
    def _create_research_and_quality(self):
        """Create research projects with varied quality."""
        print(f"\n🔬 Creating research projects...")
        
        research_count = 0
        
        for user in self.users:
            persona = user._persona
            
            # Get user's BUY transactions with journals
            user_journals = [j for j in self.journals if j.user_id == user.id]
            
            for journal in user_journals:
                if random.random() > persona.research_before_buy_prob:
                    continue
                
                quality = persona.get_research_quality()
                
                # Create research project
                project = ResearchProject(
                    user_id=user.id,
                    template_id=random.choice([20, 21, 22, 23, 24]),  # Use existing templates
                    company_id=journal.company_id,
                    project_name=f"Research: {fake.company()}",
                    status=random.choice(['completed', 'active']),
                    total_hours_spent=random.uniform(0.5, 20) * (quality / 50),  # Higher quality = more time
                    decision=random.choice(['invest', 'pass', 'watchlist']),
                )
                db.session.add(project)
                db.session.flush()  # Flush to get project.id
                research_count += 1

                # Create work sessions
                num_sessions = int(quality / 20) + 1
                for _ in range(num_sessions):
                    session = WorkSession(
                        user_id=user.id,
                        research_project_id=project.id,
                        start_time=fake.date_time_between(start_date='-6m', end_date='now'),
                        duration_minutes=random.randint(15, 120),
                        needs_followup=False,
                    )
                    db.session.add(session)
        
        db.session.commit()
        self.stats['research_projects'] = research_count
        print(f"   ✅ Created {research_count} research projects")
    
    def _create_mistakes(self):
        """Create mistake logs with semantic similarity."""
        print(f"\n🧠 Creating mistake logs...")
        
        mistake_count = 0
        
        for user in self.users:
            persona = user._persona
            
            # Disciplined investors have fewer mistakes
            if persona.name == 'disciplined_investor':
                num_mistakes = random.randint(0, 2)
            elif persona.name in ['emotional_trader', 'gambler']:
                num_mistakes = random.randint(5, 10)
            else:
                num_mistakes = random.randint(2, 5)
            
            for _ in range(num_mistakes):
                # Select pattern category based on persona
                if persona.name == 'emotional_trader':
                    pattern_key = random.choice(['fomo', 'no_research', 'averaging_down_mistake'])
                elif persona.name == 'overconfident_expert':
                    pattern_key = random.choice(['overconfidence', 'ignored_debt'])
                elif persona.name == 'gambler':
                    pattern_key = random.choice(['no_research', 'averaging_down_mistake', 'fomo'])
                else:
                    pattern_key = random.choice(list(MISTAKE_PATTERNS.keys()))
                
                pattern = random.choice(MISTAKE_PATTERNS[pattern_key])
                company = random.choice(self.companies)
                
                mistake = MistakeLog(
                    user_id=user.id,
                    company_id=company.id,
                    title=pattern['title'],
                    description=pattern['description'].format(company=company.name),
                    mistake_type=pattern_key,
                    severity=random.randint(3, 10),
                    cost_estimate=random.randint(500, 50000) if random.random() > 0.3 else None,
                    lesson_learned=fake.sentence(),
                    created_at=fake.date_time_between(start_date='-2y', end_date='now'),
                )
                db.session.add(mistake)
                mistake_count += 1
        
        db.session.commit()
        self.stats['mistakes'] = mistake_count
        print(f"   ✅ Created {mistake_count} mistake logs with semantic patterns")
    
    def _link_user_profiles(self):
        """Link users to investment profiles."""
        print(f"\n⚙️  Linking user investment profiles...")
        
        # Get existing profiles
        profiles = {p.name: p for p in InvestorProfile.query.all()}
        
        if not profiles:
            print("   ⚠️  No InvestorProfiles found. Run migration first.")
            return
        
        for user in self.users:
            persona = user._persona
            profile = profiles.get(persona.profile_type)
            
            if profile:
                user_profile = UserInvestmentProfile(
                    user_id=user.id,
                    profile_id=profile.id,
                )
                db.session.add(user_profile)
        
        db.session.commit()
        print(f"   ✅ Linked {len(self.users)} users to profiles")
    
    def _print_summary(self):
        """Print generation summary."""
        print("\n" + "="*60)
        print("✅ AI TEST DATA GENERATION COMPLETE")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"   Users: {self.stats['users_created']}")
        print(f"   Companies: {self.stats['companies_created']}")
        print(f"   Transactions: {self.stats['transactions_created']}")
        print(f"   Research Projects: {self.stats['research_projects']}")
        print(f"   Mistake Logs: {self.stats['mistakes']}")
        print(f"\n   Behavioral Patterns Generated:")
        print(f"      Averaging Down: {self.stats['patterns']['averaging_down']}")
        print(f"      Selling Early: {self.stats['patterns']['selling_early']}")
        print(f"      Holding Losers: {self.stats['patterns']['holding_losers']}")
        print(f"      Overconfidence: {self.stats['patterns']['overconfidence']}")
        print(f"\n🧪 Ready for testing:")
        print(f"   → Intelligence Engine warnings")
        print(f"   → Behavioral pattern detection")
        print(f"   → Similar mistakes (embedding search)")
        print(f"   → Research quality correlation")
        print()


# ============================================
# CLI
# ============================================

def parse_args():
    parser = argparse.ArgumentParser(description='Generate AI test data')
    parser.add_argument('--clean', action='store_true', help='Clean existing test data first')
    parser.add_argument('--users', type=int, default=CONFIG['user_count'], help='Number of users')
    parser.add_argument('--companies', type=int, default=CONFIG['companies_count'], help='Number of companies')
    parser.add_argument('--transactions', type=int, default=None, help='Max transactions per user')
    parser.add_argument('--days', type=int, default=CONFIG['history_days'], help='History in days')
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Update config from CLI
    CONFIG['user_count'] = args.users
    CONFIG['companies_count'] = args.companies
    CONFIG['history_days'] = args.days
    
    if args.transactions:
        CONFIG['transactions_per_user'] = (args.transactions // 2, args.transactions)
    
    app = create_app()
    
    with app.app_context():
        generator = AITestDataGenerator(CONFIG)
        generator.run(clean=args.clean)


if __name__ == '__main__':
    main()