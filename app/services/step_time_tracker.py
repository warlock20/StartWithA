# Investment Checklist Platform
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
Step Time Tracker Service

This service calculates time spent on different workflow step types.
Similar to StepProgressCalculator, but for time tracking and analytics.
"""

import logging
from app.models import (
    ChecklistAnalysis,
    WorkSession,
    QualitativeAnalysis
)
from app.utils.time_utils import now_utc, ensure_timezone_aware

logger = logging.getLogger(__name__)


class StepTimeTracker:
    """
    Track time spent on individual research workflow steps.
    Provides analytics on time allocation across different step types.
    """

    @staticmethod
    def get_step_time(project, step_index):
        """
        Get time spent on a specific step in minutes.

        Args:
            project: ResearchProject instance
            step_index: Index of the step in the workflow

        Returns:
            float: Time spent in minutes
        """
        if not project or not project.workflow_steps:
            return 0.0

        if step_index < 0 or step_index >= project.step_count:
            return 0.0

        # Check if we have tracked time for this step
        if project.time_per_step:
            return project.time_per_step.get(str(step_index), 0.0)

        return 0.0

    @staticmethod
    def get_time_by_step_type(project):
        """
        Get total time spent grouped by step type.

        Returns a dictionary like:
        {
            'checklist': 120.5,  # minutes
            'thesis_writing': 45.0,
            'swot': 30.0,
            ...
        }
        """
        if not project or not project.workflow_steps:
            return {}

        time_by_type = {}

        for step_index, step in enumerate(project.workflow_steps):
            step_type = step.get('type', 'unknown')
            time_spent = StepTimeTracker.get_step_time(project, step_index)

            if step_type in time_by_type:
                time_by_type[step_type] += time_spent
            else:
                time_by_type[step_type] = time_spent

        return time_by_type

    @staticmethod
    def get_active_session_time(project):
        """
        Get time spent on currently active sessions.

        Returns:
            dict: Active time by step index
        """
        active_time = {}

        active_sessions = project.work_sessions.filter(
            WorkSession.end_time.is_(None)
        ).all()

        for session in active_sessions:
            start_time_aware = ensure_timezone_aware(session.start_time)
            current_time = now_utc()
            duration_seconds = (current_time - start_time_aware).total_seconds()
            duration_minutes = duration_seconds / 60

            step_index = str(session.step_index) if session.step_index is not None else 'unknown'
            active_time[step_index] = duration_minutes

        return active_time

    @staticmethod
    def get_total_research_time(project):
        """
        Get comprehensive time breakdown for a project.

        Returns:
            dict: Complete time analytics
        """
        return {
            'total_hours': project.total_time_including_active,
            'completed_hours': project.total_hours_spent or 0.0,
            'active_hours': project.total_time_including_active - (project.total_hours_spent or 0.0),
            'time_by_step_type': StepTimeTracker.get_time_by_step_type(project),
            'time_by_step_index': project.time_per_step or {},
            'active_sessions': StepTimeTracker.get_active_session_time(project),
            'session_count': project.work_sessions.count()
        }


def calculate_checklist_time(project, step, step_index):
    """
    Calculate time spent on checklist analysis.
    Can be extended to track time within ChecklistAnalysis sessions.
    """
    return StepTimeTracker.get_step_time(project, step_index)


def calculate_thesis_writing_time(project, step, step_index):
    """Calculate time spent on thesis writing."""
    return StepTimeTracker.get_step_time(project, step_index)


def calculate_swot_time(project, step, step_index):
    """Calculate time spent on SWOT analysis."""
    return StepTimeTracker.get_step_time(project, step_index)


# Map step types to their time calculators
STEP_TIME_CALCULATORS = {
    'checklist': calculate_checklist_time,
    'thesis_writing': calculate_thesis_writing_time,
    'swot': calculate_swot_time,
}
