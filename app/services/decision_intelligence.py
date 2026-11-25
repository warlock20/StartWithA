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
Decision Intelligence (#442): the numbers behind the tabbed page.

One service per request. Research insights read the same research comparison as the
header's Research Edge, and confidence insights the same confidence stats as the
header. Holding and sector insights stay on closed outcomes (received included).
"""

import hashlib
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, List, Optional, Tuple

from flask import url_for
from sqlalchemy.orm import joinedload

from app import cache
from app.constants import (
    HIGH_QUALITY_RESEARCH_SCORE, MIN_TRADES_FOR_INSIGHTS, RECENT_DECISIONS_LIMIT,
)
from app.models import Company, PortfolioPosition, Transaction
from app.models.ai_intelligence import ResearchOutcome
from app.services.decision_quality import compare_research, research_quality_view
from app.services.decision_trades import decision_trades
from app.services.outcome_tracking import portfolio_outcomes
from app.services.portfolio_intelligence import (
    SHORT_HOLD_THRESHOLD_DAYS, LearningInsight, compare_to_expected_cagr, outcome_hold_days,
)
from app.services.position_returns import position_returns
from app.utils.portfolio_utils import (
    calculate_confidence_stats, categorize_by_holding_period, process_win_rate,
)
from app.utils.time_utils import date

TABS = ('insights', 'research', 'decision-quality', 'behaviour')
TAB_LABELS = {
    'insights': 'Your insights',
    'research': 'Research',
    'decision-quality': 'Decision quality',
    'behaviour': 'Behaviour',
}
DEFAULT_TAB = 'insights'

MAX_INSIGHTS = 6
MAX_HEADER_ALERTS = 2
IMPORTANCE_ORDER = {'high': 0, 'medium': 1, 'low': 2}

INSIGHT_KEYS = frozenset({
    'research_edge', 'research_trails', 'quality_edge', 'quality_edge_no_baseline',
    'quality_not_translating',
    'holding_long', 'holding_short', 'overconfidence', 'confidence_calibrated',
    'sector_strength', 'sector_weakness',
})

# key -> (label, endpoint, url kwargs)
# A None entry means the insight offers no next step.
INSIGHT_ACTIONS: Dict[str, Optional[Tuple[str, str, dict]]] = {
    'research_edge': ('Start new research', 'ideas.add_idea', {}),
    'quality_edge': ('Start new research', 'ideas.add_idea', {}),
    'quality_edge_no_baseline': ('See research quality', 'portfolio.analytics_decisions',
                               {'tab': 'research', '_anchor': 'research-quality'}),
    'research_trails': ('See research quality', 'portfolio.analytics_decisions',
                      {'tab': 'research', '_anchor': 'research-quality'}),
    'quality_not_translating': ('See research quality', 'portfolio.analytics_decisions',
                              {'tab': 'research', '_anchor': 'research-quality'}),
    'holding_long': ('See holding periods', 'portfolio.analytics_decisions',
                     {'tab': 'behaviour', '_anchor': 'holding-periods'}),
    'holding_short': ('See holding periods', 'portfolio.analytics_decisions',
                      {'tab': 'behaviour', '_anchor': 'holding-periods'}),
    'overconfidence': ('See calibration', 'portfolio.analytics_decisions',
                       {'tab': 'decision-quality', '_anchor': 'confidence-calibration'}),
    'confidence_calibrated': ('See calibration', 'portfolio.analytics_decisions',
                              {'tab': 'decision-quality', '_anchor': 'confidence-calibration'}),
    'sector_strength': ('Check sector allocation', 'portfolio.dashboard', {}),
    'sector_weakness': ('Check sector allocation', 'portfolio.dashboard', {}),
}

HOLDING_PERIOD_LABELS = (
    ('0-30', '0–30 days'),
    ('31-90', '31–90 days'),
    ('91-180', '91–180 days'),
    ('181-365', '181–365 days'),
    ('365+', 'Over a year'),
)
MIN_HOLDING_BUCKET_SAMPLE = MIN_TRADES_FOR_INSIGHTS
RESEARCH_EDGE_MARGIN = 5
CONFIDENCE_MARGIN = 5


def normalise_tab(value: Optional[str]) -> str:
    """The tab to show: a known tab name (case-insensitive), else the default."""
    candidate = (value or '').strip().lower()
    return candidate if candidate in TABS else DEFAULT_TAB


@dataclass
class InsightAction:
    label: str
    url: str
    tab: Optional[str]      # set only for links into this page
    anchor: Optional[str]


def insight_action(insight: LearningInsight) -> Optional[InsightAction]:
    """The next step offered under an insight, or None for an unknown key. Needs a request context."""
    entry = INSIGHT_ACTIONS.get(insight.key)
    if entry is None:
        return None
    label, endpoint, kwargs = entry
    return InsightAction(
        label=label,
        url=url_for(endpoint, **kwargs),
        tab=kwargs.get('tab'),
        anchor=kwargs.get('_anchor'),
    )


class DecisionIntelligenceService:
    def __init__(self, user_id: int, as_of: Optional[date] = None):
        self.user_id = user_id
        self.as_of = as_of

    # ---- shared data, computed once per service ----

    @cached_property
    def trades(self) -> list:
        return decision_trades(self.user_id, self.as_of)

    @cached_property
    def comparison(self):
        return compare_research(self.trades)

    @cached_property
    def confidence_stats(self) -> dict:
        rows = [{'confidence': t.confidence, 'return': t.return_pct}
                for t in self.trades if t.confidence is not None]
        return calculate_confidence_stats(rows)

    @cached_property
    def expectations(self) -> List[dict]:
        rows = []
        for t in self.trades:
            if t.expected_cagr is None:
                continue
            vs_target = compare_to_expected_cagr(t.expected_cagr, t.return_pct, t.days, t.annualized_pct)
            rows.append({
                'company': t.outcome.company,
                'entry_date': t.entry_date,
                'exit_date': t.exit_date,
                'expected': vs_target.expected,
                'actual': vs_target.actual,
                'annualized': vs_target.annualized,
                'diff': vs_target.actual - vs_target.expected,
                'met': vs_target.actual >= vs_target.expected,
            })
        rows.sort(key=lambda r: r['diff'], reverse=True)
        return rows

    @cached_property
    def closed_outcomes(self) -> List[ResearchOutcome]:
        return portfolio_outcomes(self.user_id).filter(
            ResearchOutcome.realized_return_pct.isnot(None)
        ).options(
            joinedload(ResearchOutcome.company).joinedload(Company.sector)
        ).all()

    @cached_property
    def _matrix(self) -> dict:
        research, none = self.comparison.research, self.comparison.none
        earned = sum(1 for t in research.trades if t.is_gain)
        lucky = sum(1 for t in none.trades if t.is_gain)
        return {
            'earned': earned,
            'unlucky': research.count - earned,
            'lucky': lucky,
            'expected': none.count - lucky,
        }

    @cached_property
    def _expectation_counts(self) -> Tuple[int, int, float]:
        met = sum(1 for r in self.expectations if r['met'])
        total = len(self.expectations)
        return met, total, (met / total * 100) if total else 0.0

    @property
    def _confidence_diff(self) -> Optional[float]:
        high, medium = self.confidence_stats['high'], self.confidence_stats['medium']
        if not (high['count'] and medium['count']):
            return None
        return high['avg_return'] - medium['avg_return']

    # ---- insights ----

    @cached_property
    def _insight_list(self) -> List[LearningInsight]:
        if len(self.closed_outcomes) < MIN_TRADES_FOR_INSIGHTS:
            return []
        insights = (
            self._research_insights()
            + self._quality_insights()
            + self._holding_insights()
            + self._confidence_insights()
            + self._sector_insights()
        )
        insights.sort(key=lambda i: IMPORTANCE_ORDER.get(i.importance, 99))
        return insights[:MAX_INSIGHTS]

    def _research_insights(self) -> List[LearningInsight]:
        edge = self.comparison.edge
        if edge is None:
            return []
        research, none = self.comparison.research, self.comparison.none
        if edge > RESEARCH_EDGE_MARGIN:
            return [LearningInsight(
                category='edge',
                title='Research pays off for you',
                description=f'Trades you researched returned {edge:.1f} points more than trades made without research.',
                supporting_data=f"{research.count} researched vs {none.count} without research, open trades at today's price",
                importance='high',
                key='research_edge',
            )]
        if edge < 0:
            return [LearningInsight(
                category='warning',
                title='Research is not paying off yet',
                description=f'Trades you researched returned {abs(edge):.1f} points less than trades made without research.',
                supporting_data=f"{research.count} researched vs {none.count} without research, open trades at today's price",
                importance='high',
                key='research_trails',
            )]
        return []

    def _quality_insights(self) -> List[LearningInsight]:
        high, low = self.comparison.high, self.comparison.low
        if not (high.count and low.count):
            return []
        hq_avg, lq_avg = high.avg_return, low.avg_return
        data = f'High quality: {hq_avg:.1f}% avg, Low quality: {lq_avg:.1f}% avg'
        if hq_avg > lq_avg + 5:
            edge = self.comparison.edge
            if edge is not None and edge < 0:
                # The header says research trails; an "edge" card would contradict it
                return [LearningInsight(
                    category='improvement',
                    title='Better research beats weaker research',
                    description=f'High-quality research returned {hq_avg - lq_avg:.1f} points more than low-quality research, but researched trades still trail trades made without research.',
                    supporting_data=data,
                    importance='medium',
                    key='quality_edge_no_baseline',
                )]
            return [LearningInsight(
                category='edge',
                title='Research Quality Is Your Edge',
                description=f'High-quality research (score {HIGH_QUALITY_RESEARCH_SCORE}+) delivers {hq_avg - lq_avg:.1f}% better returns than low-quality research.',
                supporting_data=data,
                importance='high',
                key='quality_edge',
            )]
        if lq_avg > hq_avg:
            return [LearningInsight(
                category='warning',
                title='Research Quality Not Translating',
                description="Your high-quality research isn't outperforming. Consider if your research process needs adjustment.",
                supporting_data=data,
                importance='high',
                key='quality_not_translating',
            )]
        return []

    def _holding_insights(self) -> List[LearningInsight]:
        short_holds, long_holds = [], []
        for o in self.closed_outcomes:
            days = outcome_hold_days(o)
            if days is None:
                continue
            (short_holds if days < SHORT_HOLD_THRESHOLD_DAYS else long_holds).append(float(o.realized_return_pct))
        if not (short_holds and long_holds):
            return []
        short_avg = sum(short_holds) / len(short_holds)
        long_avg = sum(long_holds) / len(long_holds)
        if long_avg > short_avg + 5:
            return [LearningInsight(
                category='winning_pattern',
                title='Patience Pays Off',
                description=f'Positions held 90+ days return {long_avg - short_avg:.1f}% more on average.',
                supporting_data=f'Closed trades: long holds {long_avg:.1f}% avg ({len(long_holds)} trades), short holds {short_avg:.1f}% avg ({len(short_holds)} trades)',
                importance='high',
                key='holding_long',
            )]
        if short_avg > long_avg + 5:
            return [LearningInsight(
                category='winning_pattern',
                title='Quick Trades Working',
                description='Your shorter-term trades (<90 days) are outperforming.',
                supporting_data=f'Closed trades: short holds {short_avg:.1f}% avg ({len(short_holds)} trades), long holds {long_avg:.1f}% avg ({len(long_holds)} trades)',
                importance='medium',
                key='holding_short',
            )]
        return []

    def _confidence_insights(self) -> List[LearningInsight]:
        diff = self._confidence_diff
        if diff is None:
            return []
        high, medium = self.confidence_stats['high'], self.confidence_stats['medium']
        data = f"High confidence: {high['avg_return']:.1f}% avg ({high['count']} buys), Medium confidence: {medium['avg_return']:.1f}% avg ({medium['count']} buys)"
        if diff < 0:
            return [LearningInsight(
                category='warning',
                title='Conviction is not predicting returns',
                description=f'Buys you scored 8 to 10 on confidence returned {abs(diff):.1f} points less than the ones you scored 5 to 7.',
                supporting_data=data,
                importance='high',
                key='overconfidence',
            )]
        if diff > CONFIDENCE_MARGIN:
            return [LearningInsight(
                category='edge',
                title='Well calibrated confidence',
                description=f'Buys you scored 8 to 10 returned {diff:.1f} points more than the ones you scored 5 to 7.',
                supporting_data=data,
                importance='medium',
                key='confidence_calibrated',
            )]
        return []

    def _sector_insights(self) -> List[LearningInsight]:
        sector_returns: Dict[str, List[float]] = {}
        for o in self.closed_outcomes:
            company = o.company
            if company and company.sector:
                sector_returns.setdefault(company.sector.display_name, []).append(float(o.realized_return_pct))
        if len(sector_returns) < 2:
            return []
        sector_avgs = {
            sector: sum(returns) / len(returns)
            for sector, returns in sector_returns.items() if len(returns) >= 2
        }
        if not sector_avgs:
            return []
        insights = []
        best = max(sector_avgs, key=sector_avgs.get)
        worst = min(sector_avgs, key=sector_avgs.get)
        if sector_avgs[best] > 10:
            insights.append(LearningInsight(
                category='winning_pattern',
                title=f'{best} Is Your Sweet Spot',
                description=f"You're averaging {sector_avgs[best]:.1f}% returns in {best}.",
                supporting_data=f'{len(sector_returns[best])} trades',
                importance='medium',
                key='sector_strength',
            ))
        if sector_avgs[worst] < -5:
            insights.append(LearningInsight(
                category='warning',
                title=f'Struggling in {worst}',
                description=f'Your {worst} trades average {sector_avgs[worst]:.1f}%. Consider avoiding or researching more carefully.',
                supporting_data=f'{len(sector_returns[worst])} trades',
                importance='medium',
                key='sector_weakness',
            ))
        return insights

    def learning_insights(self) -> List[LearningInsight]:
        return list(self._insight_list)

    # ---- tabs ----

    def header(self) -> dict:
        matrix = self._matrix
        met, total, met_pct = self._expectation_counts
        diff = self._confidence_diff
        durations = [d for d in (outcome_hold_days(o) for o in self.closed_outcomes) if d is not None]
        warnings = [i for i in self._insight_list if i.category == 'warning'][:MAX_HEADER_ALERTS]
        return {
            'research_edge': self.comparison.edge,
            'process_win_rate': process_win_rate(matrix['earned'], matrix['unlucky']),
            'researched_wins': matrix['earned'],
            'researched_count': self.comparison.research.count,
            'confidence_calibrated': None if diff is None else diff > 0,
            'confidence_high_return': self.confidence_stats['high']['avg_return'],
            'expectations_met_count': met,
            'expectations_total_count': total,
            'expectations_met_pct': met_pct,
            'completed_trades': len(self.closed_outcomes),
            'avg_hold_days': sum(durations) // len(durations) if durations else 0,
            'alerts': [self._alert(i) for i in warnings],
        }

    @staticmethod
    def _alert(insight: LearningInsight) -> dict:
        message = f'{insight.title}: {insight.description}'
        digest = hashlib.sha1(message.encode()).hexdigest()[:10]
        return {'message': message, 'id': f'{insight.key}:{digest}'}

    def insights(self) -> dict:
        closed = len(self.closed_outcomes)
        return {
            'locked': closed < MIN_TRADES_FOR_INSIGHTS,
            'closed_count': closed,
            'needed': MIN_TRADES_FOR_INSIGHTS,
            'cards': [{'insight': i, 'action': insight_action(i)} for i in self._insight_list],
        }

    def research(self) -> dict:
        return {
            'view': research_quality_view(self.trades),
            'high_score': HIGH_QUALITY_RESEARCH_SCORE,
            'has_trades': bool(self.trades),
        }

    def decision_quality(self) -> dict:
        matrix = self._matrix
        met, total, met_pct = self._expectation_counts
        diff = self._confidence_diff
        return {
            'matrix': matrix,
            'imported_unknown': self.comparison.unknown.count,
            'has_matrix': self.comparison.research.count + self.comparison.none.count > 0,
            'process_win_rate': process_win_rate(matrix['earned'], matrix['unlucky']),
            'confidence_stats': self.confidence_stats,
            'confidence_calibrated': None if diff is None else diff > 0,
            'confidence_diff': diff,
            'has_confidence': any(s['count'] for s in self.confidence_stats.values()),
            'expectations': self.expectations,
            'expectations_met_count': met,
            'expectations_total_count': total,
            'expectations_met_pct': met_pct,
        }

    def behaviour(self) -> dict:
        positions = PortfolioPosition.query.filter_by(user_id=self.user_id).all()
        active = [p for p in positions if p.is_active]
        buckets = categorize_by_holding_period(active, position_returns(positions))
        rows = []
        for key, label in HOLDING_PERIOD_LABELS:
            returns = buckets[key]
            count = len(returns)
            rows.append({
                'key': key,
                'label': label,
                'count': count,
                'avg_return': round(sum(returns) / count, 1) if count else 0.0,
                'win_rate': sum(1 for r in returns if r > 0) / count * 100 if count else 0.0,
                'small_sample': count < MIN_HOLDING_BUCKET_SAMPLE,
            })
        return {
            'holding_periods': rows,
            'has_open_positions': bool(active),
            'recent': self._recent_decisions(),
        }

    def _recent_decisions(self) -> List[dict]:
        transactions = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.type.in_(['BUY', 'SELL']),
        ).options(
            joinedload(Transaction.company),
            joinedload(Transaction.decision_journal),
        ).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(RECENT_DECISIONS_LIMIT).all()

        by_opening = {t.opening.id: t for t in self.trades if t.opening is not None}
        rows = []
        for txn in transactions:
            journal = txn.decision_journal
            if txn.type == 'SELL':
                kind, research = 'SELL', None
            else:
                is_top_up = journal is not None and journal.is_top_up
                kind = 'TOP-UP' if is_top_up else 'BUY'
                # The chip follows the trade the decision belongs to, as the header counts it
                opening_id = None if journal is None else (journal.parent_decision_id if is_top_up else journal.id)
                trade = by_opening.get(opening_id)
                if trade is None:
                    research = None
                elif trade.research in ('low', 'high'):
                    research = 'Researched'
                elif trade.research == 'none':
                    research = 'No research'
                else:
                    research = None
            rows.append({'transaction': txn, 'kind': kind, 'research': research})
        return rows

    def tab(self, name: str) -> dict:
        handlers = {
            'insights': self.insights,
            'research': self.research,
            'decision-quality': self.decision_quality,
            'behaviour': self.behaviour,
        }
        if name not in handlers:
            raise ValueError(f'Unknown tab: {name!r}')
        return handlers[name]()


@cache.memoize(timeout=1800)  # 30 min: trade history doesn't change often
def get_learning_insights(user_id: int) -> List[LearningInsight]:
    """The cached insight list (no request context needed), for the dashboard alert."""
    return DecisionIntelligenceService(user_id).learning_insights()
