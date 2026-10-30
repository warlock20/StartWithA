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

from flask import current_app
from sqlalchemy.orm.attributes import flag_modified

from app.models import ChecklistAnalysis, ChecklistAnswer, ResearchProject
from app.services.export_service import resolve_checklist_id


def _project_step(analysis):
    """(project, step_index) for the checklist step a session belongs to, or (None, None).

    A user has one project per company and a session is one checklist on one company, so the
    link comes from the database. The `research_context` Flask-session cookie only remembers the
    last project step the user opened, which may be a different company's project.
    """
    project = ResearchProject.query.filter_by(user_id=analysis.user_id, company_id=analysis.company_id).first()
    if project:
        for step_index, step in enumerate(project.workflow_steps):
            if step.get('type') == 'checklist' and resolve_checklist_id(project, step_index, step) == analysis.checklist_id:
                return project, step_index
    return None, None


def project_step_for_analysis(analysis):
    """The research project step a checklist session belongs to, as template context, or None."""
    project, step_index = _project_step(analysis)
    if not project:
        return None
    return {
        'project_id': project.id,
        'step_index': step_index,
        'can_complete': project.status == 'active' and step_index not in (project.completed_steps or []),
    }


def refresh_checklist_step_notes(analysis):
    """Rebuild a completed checklist step's saved summary after a verdict changes.

    The summary is written to `project.step_notes` when the step is completed and is what the
    companion, AI context, exports and project pages read, so a later verdict change must reach
    it. Steps not yet completed, and steps the user skipped, are left alone. The caller commits.
    Returns True when the saved summary was rewritten.
    """
    project, step_index = _project_step(analysis)
    if not project or step_index not in (project.completed_steps or []):
        return False
    notes = project.step_notes or {}
    if notes.get(str(step_index)) == '[SKIPPED]':
        return False
    summary = checklist_session_summary(analysis, project.company)
    if notes.get(str(step_index)) == summary:
        return False
    project.step_notes = {**notes, str(step_index): summary}
    flag_modified(project, 'step_notes')
    return True


def collect_research_session_summary(project, step_index):
    """
    Collect and summarize the actual research data from the step's checklist session
    """
    try:
        if not project.company_id:
            return "Completed research checklist evaluation (no company data)"

        step = project.get_step(step_index)
        checklist_id = resolve_checklist_id(project, step_index, step) if step else None
        session = ChecklistAnalysis.query.filter_by(
            user_id=project.user_id,
            company_id=project.company_id,
            checklist_id=checklist_id
        ).first() if checklist_id else None

        if not session:
            return "Completed research checklist evaluation (no research session found)"

        return checklist_session_summary(session, project.company)

    except Exception:
        current_app.logger.exception('Error collecting research session summary')
        return "Completed research checklist evaluation (details unavailable)."


def checklist_session_summary(session, company):
    """Markdown summary of a checklist session's verdicts, as saved into a project step's notes."""
    research_answers = ChecklistAnswer.query.filter_by(
        checklist_analysis_id=session.id
    ).all()

    if not research_answers:
        return f"Completed research evaluation using {session.checklist.name} (no answers recorded)"

    # Build summary from the research answers
    summary_parts = [
        f"**Research Summary: {session.checklist.name}**",
        f"Company: {company.name} ({company.ticker_symbol})",
        f"Completed: {session.start_date.strftime('%Y-%m-%d')}",
        "",
        "**Key Research Findings:**"
    ]

    # Categorize answers by satisfaction status
    satisfied_items = []
    not_satisfied_items = []
    needs_attention_items = []
    informational_items = []

    for answer in research_answers:
        item_text = answer.item.text[:100] + "..." if len(answer.item.text) > 100 else answer.item.text

        if answer.satisfaction_status == 'satisfied':
            satisfied_items.append(f"✅ {item_text}")
        elif answer.satisfaction_status == 'not_satisfied':
            not_satisfied_items.append(f"❌ {item_text}")
        elif answer.satisfaction_status == 'needs_attention':
            needs_attention_items.append(f"⚠️ {item_text}")
        else:
            informational_items.append(f"ℹ️ {item_text}")

    # Add categorized findings
    if satisfied_items:
        summary_parts.append("\n**Positive Findings:**")
        summary_parts.extend(satisfied_items[:5])  # Limit to top 5

    if not_satisfied_items:
        summary_parts.append("\n**Concerns:**")
        summary_parts.extend(not_satisfied_items[:5])

    if needs_attention_items:
        summary_parts.append("\n**Needs Attention:**")
        summary_parts.extend(needs_attention_items[:5])

    # Add summary statistics
    total_items = len(research_answers)
    satisfied_count = len(satisfied_items)
    pass_rate = round((satisfied_count / total_items) * 100) if total_items > 0 else 0

    summary_parts.extend([
        "",
        f"**Summary Stats:**",
        f"- Total Items Evaluated: {total_items}",
        f"- Satisfied: {satisfied_count} ({pass_rate}%)",
        f"- Concerns: {len(not_satisfied_items)}",
        f"- Needs Attention: {len(needs_attention_items)}"
    ])

    return "\n".join(summary_parts)
