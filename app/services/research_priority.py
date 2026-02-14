"""
Research Priority Service

Computes priority scores (0-100) for active research projects to help
the user decide what to work on next. Higher score = work on this first.

Factors:
- Momentum (default 40%): Recent work = high score, exponential decay
- Proximity to done (default 25%): Concave curve rewarding near-completion
- Staleness pressure (default 20%): Bell curve peaking at ~10 days idle
- Investment signal (default 15%): Green/red flags + pending followups
"""

import math
from dataclasses import dataclass, field

from app.models import ResearchProject, ResearchSettings
from app.utils.time_utils import now_utc, ensure_timezone_aware


@dataclass
class ProjectScore:
    """Score breakdown for a single research project."""
    project: object
    total: float = 0.0
    momentum: float = 0.0
    proximity: float = 0.0
    staleness: float = 0.0
    signal: float = 0.0
    label: str = ''
    days_idle: int = 0
    is_stale_warning: bool = False
    staleness_tier: int = 0


@dataclass
class FocusRecommendation:
    """The complete recommendation for the dashboard."""
    hero: ProjectScore = None
    runners_up: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    active_count: int = 0
    project_limit: int = 3


class ResearchPriorityService:

    @staticmethod
    def score_project(project, settings):
        """
        Compute priority score for a single project.

        Args:
            project: ResearchProject instance (status must be 'active')
            settings: ResearchSettings instance with tunable parameters

        Returns:
            ProjectScore with total (0-100) and subscores
        """
        score = ProjectScore(project=project)

        # --- Days idle ---
        if project.last_worked_at:
            last_worked_aware = ensure_timezone_aware(project.last_worked_at)
            delta = now_utc() - last_worked_aware
            score.days_idle = max(0, delta.days)
        else:
            # Never worked on — use created_at
            created_aware = ensure_timezone_aware(project.created_at)
            delta = now_utc() - created_aware
            score.days_idle = max(0, delta.days)

        # --- Momentum (exponential decay) ---
        # Half-life: after N days, momentum halves. e.g., half_life=3:
        #   0 days -> 1.0, 3 days -> 0.5, 6 days -> 0.25
        half_life = max(1, settings.momentum_half_life_days)
        decay = math.exp(-0.693 * score.days_idle / half_life)  # ln(2) ≈ 0.693
        score.momentum = decay * settings.weight_momentum

        # --- Proximity to done (concave curve) ---
        # (progress/100)^0.7 — rewards near-completion disproportionately
        # 80% -> 0.86, 50% -> 0.62, 20% -> 0.30
        progress_pct = project.progress_percentage or 0.0
        proximity_raw = (progress_pct / 100.0) ** 0.7 if progress_pct > 0 else 0.0
        score.proximity = proximity_raw * settings.weight_proximity

        # --- Staleness pressure (bell curve) ---
        # Peaks at staleness_peak_days, drops off on both sides.
        # Uses a Gaussian centered at peak_days with sigma = peak_days/2
        peak = max(1, settings.staleness_peak_days)
        sigma = peak / 2.0
        staleness_raw = math.exp(-0.5 * ((score.days_idle - peak) / sigma) ** 2)
        score.staleness = staleness_raw * settings.weight_staleness

        # --- Investment signal ---
        # green_flags - red_flags + followup urgency, normalized to [0, 1]
        green_count = len(project.green_flags) if project.green_flags else 0
        red_count = len(project.red_flags) if project.red_flags else 0

        # Check for pending followups in recent work sessions
        followup_count = 0
        if project.work_sessions:
            followup_count = project.work_sessions.filter_by(needs_followup=True).count()

        # Raw signal: green flags are positive, red flags reduce but don't go below 0,
        # followups add urgency
        signal_raw = max(0, green_count - red_count) + (followup_count * 2)
        # Normalize: cap at 10 signals for full score
        signal_normalized = min(1.0, signal_raw / 10.0)
        score.signal = signal_normalized * settings.weight_signal

        # --- Total ---
        score.total = round(score.momentum + score.proximity + score.staleness + score.signal, 1)

        # --- Label ---
        score.label = ResearchPriorityService.get_recommendation_label(score.total)

        # --- Staleness tier ---
        if score.days_idle >= settings.stale_nudge_days and progress_pct < settings.stale_warning_min_progress:
            score.staleness_tier = 2
            score.is_stale_warning = True
        elif score.days_idle >= settings.stale_warning_days:
            score.staleness_tier = 1
            score.is_stale_warning = score.days_idle > settings.stale_warning_days and progress_pct < settings.stale_warning_min_progress
        else:
            score.staleness_tier = 0
            score.is_stale_warning = False

        return score

    @staticmethod
    def get_recommendation_label(total_score):
        """Map score to a human-readable recommendation label."""
        if total_score > 70:
            return 'Continue next'
        elif total_score >= 40:
            return 'Needs attention'
        else:
            return 'Consider pausing'

    @staticmethod
    def rank_projects(user):
        """
        Score and rank all active projects for a user.

        Args:
            user: User instance

        Returns:
            List of ProjectScore, sorted by total desc (tie-break: progress %)
        """
        settings = ResearchSettings.get_or_create(user.id)

        active_projects = user.research_projects.filter(
            ResearchProject.status.in_(['active'])
        ).all()

        scored = [
            ResearchPriorityService.score_project(p, settings)
            for p in active_projects
        ]

        # Sort by total score desc, tie-break by progress % desc
        scored.sort(key=lambda s: (s.total, s.project.progress_percentage or 0), reverse=True)

        return scored

    @staticmethod
    def get_focus_recommendation(user):
        """
        Build the complete focus recommendation for the dashboard.

        Args:
            user: User instance

        Returns:
            FocusRecommendation with hero project, runners-up, and warnings
        """
        settings = ResearchSettings.get_or_create(user.id)
        ranked = ResearchPriorityService.rank_projects(user)

        rec = FocusRecommendation(
            active_count=len(ranked),
            project_limit=settings.active_project_limit,
        )

        if ranked:
            rec.hero = ranked[0]
            rec.runners_up = ranked[1:]

        # --- Warnings ---
        if len(ranked) > settings.active_project_limit:
            over_by = len(ranked) - settings.active_project_limit
            rec.warnings.append({
                'type': 'over_limit',
                'message': f'{len(ranked)} active projects \u2014 your focus limit is {settings.active_project_limit}. Consider pausing or killing {over_by}.',
            })

        for s in ranked:
            if s.is_stale_warning:
                rec.warnings.append({
                    'type': 'stale_project',
                    'message': f'{s.project.subject_display_name} has been idle {s.days_idle} days with only {s.project.progress_percentage:.0f}% progress. Move to Too Hard?',
                    'project_id': s.project.id,
                })

        return rec
