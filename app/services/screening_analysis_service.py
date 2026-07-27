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
Screening Analysis Service

Gathers and formats kill checklist data for AI-powered analysis.
Used by the analytics dashboard's Initial Screening tab.
"""

from collections import defaultdict
from sqlalchemy.orm import joinedload
from app.models import (KillChecklist, KillCriterion, KillSession,
                        KillAnswer, IdeaPipeline)

MIN_SESSIONS = 5


class ScreeningAnalysisService:

    @staticmethod
    def has_sufficient_data(user_id):
        """Check if user has enough kill data for meaningful analysis.

        Returns:
            (can_analyze: bool, stats: dict)
        """
        completed_sessions = KillSession.query.filter_by(
            user_id=user_id
        ).filter(
            KillSession.completed_at.isnot(None)
        ).count()

        return (
            completed_sessions >= MIN_SESSIONS,
            {
                'completed_sessions': completed_sessions,
                'minimum_required': MIN_SESSIONS,
            }
        )

    @staticmethod
    def gather_screening_data(user_id):
        """Gather all kill checklist data for LLM analysis.

        Returns a structured dict with checklist summaries, session details,
        criteria stats, and sector breakdown.
        """
        # ── Checklists with criteria ──
        checklists = KillChecklist.query.filter_by(user_id=user_id).all()

        checklist_summaries = []
        for cl in checklists:
            criteria_list = KillCriterion.query.filter_by(
                kill_checklist_id=cl.id
            ).order_by(KillCriterion.order).all()

            checklist_summaries.append({
                'name': cl.name,
                'total_evaluated': cl.total_ideas_evaluated,
                'total_killed': cl.total_ideas_killed,
                'kill_rate': cl.kill_rate,
                'criteria': [
                    {
                        'question': c.question,
                        'times_evaluated': c.times_evaluated,
                        'times_failed': c.times_failed,
                        'fail_rate': round(
                            c.times_failed / c.times_evaluated * 100, 1
                        ) if c.times_evaluated > 0 else 0,
                    }
                    for c in criteria_list
                ],
            })

        # ── Completed sessions with answers and idea metadata ──
        sessions = KillSession.query.filter_by(user_id=user_id).filter(
            KillSession.completed_at.isnot(None)
        ).options(
            joinedload(KillSession.idea).joinedload(IdeaPipeline.sector),
        ).order_by(KillSession.completed_at.desc()).all()

        session_details = []
        sector_counts = defaultdict(lambda: {'evaluated': 0, 'killed': 0})

        for s in sessions:
            idea = s.idea
            if not idea:
                continue

            sector_name = (
                idea.sector.display_name if idea.sector else 'Unknown'
            )

            # Track sector breakdown
            sector_counts[sector_name]['evaluated'] += 1
            if s.outcome == 'killed':
                sector_counts[sector_name]['killed'] += 1

            # Get the failed criterion question
            failed_question = None
            if idea.failed_criterion_id:
                criterion = KillCriterion.query.get(idea.failed_criterion_id)
                if criterion:
                    failed_question = criterion.question

            # Get answer notes for this session
            answers = KillAnswer.query.filter_by(
                kill_session_id=s.id
            ).all()
            answer_notes = [
                a.notes for a in answers
                if a.notes and a.notes.strip()
            ]

            session_details.append({
                'idea_name': idea.name,
                'sector': sector_name,
                'source': idea.source or 'Unknown',
                'outcome': s.outcome,
                'failed_criterion': failed_question,
                'notes': answer_notes[:3],  # Limit notes per session
                'date': s.completed_at.strftime('%Y-%m-%d') if s.completed_at else None,
            })

        # ── Criteria stats (aggregated across all checklists) ──
        all_criteria = []
        for cl_summary in checklist_summaries:
            all_criteria.extend(cl_summary['criteria'])

        criteria_stats = sorted(
            [c for c in all_criteria if c['times_evaluated'] > 0],
            key=lambda x: x['fail_rate'],
            reverse=True
        )

        # ── Sector breakdown ──
        sector_breakdown = sorted(
            [
                {'sector': name, **counts}
                for name, counts in sector_counts.items()
            ],
            key=lambda x: x['evaluated'],
            reverse=True
        )

        return {
            'checklist_summaries': checklist_summaries,
            'sessions': session_details,
            'criteria_stats': criteria_stats,
            'sector_breakdown': sector_breakdown,
            'total_sessions': len(session_details),
            'total_killed': sum(
                1 for s in session_details if s['outcome'] == 'killed'
            ),
        }

    @staticmethod
    def format_for_llm(data):
        """Format gathered data into compact text for LLM prompt.

        Keeps output under ~3000 words to stay within token limits.
        """
        lines = []

        # ── Summary ──
        lines.append('## Kill Checklist Summary')
        for cl in data['checklist_summaries']:
            lines.append(
                f"- Checklist \"{cl['name']}\": {cl['total_evaluated']} ideas "
                f"evaluated, {cl['total_killed']} killed "
                f"({cl['kill_rate']}% kill rate)"
            )
            lines.append(f"  Criteria count: {len(cl['criteria'])}")
        lines.append('')

        # ── Top criteria by fail rate ──
        lines.append('## Top Criteria by Kill Rate')
        for i, c in enumerate(data['criteria_stats'][:15], 1):
            lines.append(
                f"{i}. \"{c['question']}\" — Failed {c['times_failed']}/"
                f"{c['times_evaluated']} times ({c['fail_rate']}%)"
            )
        lines.append('')

        # ── Recent sessions (last 20) ──
        lines.append('## Recent Kill Sessions')
        for s in data['sessions'][:20]:
            outcome_label = s['outcome'].upper() if s['outcome'] else 'UNKNOWN'
            line = (
                f"- [{s['date']}] \"{s['idea_name']}\" "
                f"(Sector: {s['sector']}, Source: {s['source']}) "
                f"→ {outcome_label}"
            )
            if s['failed_criterion']:
                line += f"\n  Failed on: \"{s['failed_criterion']}\""
            if s['notes']:
                notes_text = '; '.join(s['notes'][:2])
                if len(notes_text) > 200:
                    notes_text = notes_text[:200] + '...'
                line += f"\n  Notes: {notes_text}"
            lines.append(line)
        lines.append('')

        # ── Sector breakdown ──
        lines.append('## Sector Breakdown')
        for sb in data['sector_breakdown']:
            kill_pct = round(
                sb['killed'] / sb['evaluated'] * 100
            ) if sb['evaluated'] > 0 else 0
            lines.append(
                f"- {sb['sector']}: {sb['evaluated']} evaluated, "
                f"{sb['killed']} killed ({kill_pct}%)"
            )
        lines.append('')

        # ── Aggregate stats ──
        lines.append('## Aggregate Stats')
        lines.append(f"- Total completed sessions: {data['total_sessions']}")
        lines.append(f"- Total killed: {data['total_killed']}")
        overall_kill_rate = round(
            data['total_killed'] / data['total_sessions'] * 100
        ) if data['total_sessions'] > 0 else 0
        lines.append(f"- Overall kill rate: {overall_kill_rate}%")

        return '\n'.join(lines)
