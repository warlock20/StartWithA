"""
Research Project Export
Export a full research project as a ZIP of markdown files + attachments.
"""

import io
import os
import zipfile
from datetime import datetime
from flask import current_app, abort, Response
from flask_login import current_user, login_required
from app.models import (ResearchProject, ResearchAttachment,
                        FreeResearchQuestion, ChecklistAnalysis, ChecklistAnswer)
from app.research_workflow import research_workflow_bp
from app.utils.blocknote_utils import blocknote_to_text
from app.research_workflow.checklist_check_routes import get_all_ordered_items_for_checklist
from app.research_workflow.pdf_report import generate_pdf_report
import logging

logger = logging.getLogger(__name__)


def _safe_name(text):
    """Convert text to a safe filename component"""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in (text or 'Unknown')).strip()


def _build_readme(project):
    """Build the README.md overview file"""
    lines = []
    company = project.company
    lines.append(f"# Research Project: {company.name}")
    if company.ticker_symbol:
        lines.append(f"**Ticker:** {company.ticker_symbol}")

    sector_name = None
    if project.sector:
        sector_name = project.sector.display_name
    elif company.sector:
        sector_name = company.sector.display_name
    if sector_name:
        lines.append(f"**Sector:** {sector_name}")

    lines.append(f"**Template:** {project.template.name}")
    lines.append(f"**Status:** {project.status}")
    if project.decision:
        lines.append(f"**Decision:** {project.decision.title()}")
        if project.decision_confidence:
            lines.append(f"**Confidence:** {project.decision_confidence}/10")
        if project.decision_date:
            lines.append(f"**Decision Date:** {project.decision_date.strftime('%Y-%m-%d')}")

    lines.append(f"**Total Time Invested:** {round(project.total_hours_spent or 0, 1)} hours")
    lines.append(f"**Steps Completed:** {len(project.completed_steps or [])} of {project.template.step_count}")

    if project.last_worked_at:
        lines.append(f"**Last Worked:** {project.last_worked_at.strftime('%Y-%m-%d')}")

    if project.investment_thesis:
        lines.append("\n## Investment Thesis\n")
        lines.append(project.investment_thesis)

    if project.green_flags:
        lines.append("\n## Green Flags\n")
        for flag in project.green_flags:
            lines.append(f"- {flag}")

    if project.red_flags:
        lines.append("\n## Red Flags\n")
        for flag in project.red_flags:
            lines.append(f"- {flag}")

    if project.key_findings:
        lines.append("\n## Key Findings\n")
        for finding in project.key_findings:
            lines.append(f"- {finding}")

    return "\n".join(lines)


def _build_step_file(project, step_index, step):
    """Build a markdown file for a single workflow step"""
    lines = []
    lines.append(f"# Step {step_index + 1}: {step['name']}")
    lines.append(f"**Type:** {step.get('type', 'research').replace('_', ' ').title()}")

    time_spent = (project.time_per_step or {}).get(str(step_index), 0)
    if time_spent:
        lines.append(f"**Time Spent:** {round(time_spent)} minutes")

    is_completed = step_index in (project.completed_steps or [])
    lines.append(f"**Status:** {'Completed' if is_completed else 'Not completed'}")

    # Step notes
    notes = (project.step_notes or {}).get(str(step_index), '')
    if notes and notes != '[SKIPPED]':
        lines.append("\n## Notes\n")
        # Try to convert from BlockNote JSON, fall back to plain text
        text = blocknote_to_text(notes) if notes.startswith('[') else notes
        lines.append(text if text else notes)
    elif notes == '[SKIPPED]':
        lines.append("\n*This step was skipped.*")

    # Free research questions
    if step.get('type') == 'free_research':
        questions = FreeResearchQuestion.query.filter_by(
            project_id=project.id,
            step_index=step_index
        ).order_by(FreeResearchQuestion.order_index).all()

        if questions:
            lines.append("\n## Research Questions\n")
            for i, q in enumerate(questions, 1):
                status = 'Answered' if q.status == 'answered' else 'Exploring'
                lines.append(f"### Q{i}: {q.question_text}")
                lines.append(f"**Status:** {status}\n")
                if q.answer_content:
                    answer_text = blocknote_to_text(q.answer_content)
                    if answer_text:
                        lines.append(answer_text)
                lines.append("")

    # Checklist answers
    if step.get('type') == 'checklist' and project.company_id:
        checklist_id = step.get('config', {}).get('checklist_id')
        if checklist_id:
            analysis = ChecklistAnalysis.query.filter_by(
                user_id=project.user_id,
                checklist_id=int(checklist_id),
                company_id=project.company_id
            ).order_by(ChecklistAnalysis.start_date.desc()).first()

            if analysis:
                answers = ChecklistAnswer.query.filter_by(
                    checklist_analysis_id=analysis.id
                ).all()
                answers_map = {a.checklist_item_id: a for a in answers}
                all_items = get_all_ordered_items_for_checklist(int(checklist_id))

                if all_items:
                    lines.append("\n## Checklist Answers\n")
                    for item in all_items:
                        answer = answers_map.get(item.id)
                        lines.append(f"**{item.text}**")
                        if answer:
                            status = (answer.satisfaction_status or 'not set').replace('_', ' ').title()
                            lines.append(f"- Status: {status}")
                            if answer.answer_text:
                                lines.append(f"- Answer: {blocknote_to_text(answer.answer_text)}")
                        else:
                            lines.append("- Not answered")
                        lines.append("")

    # Step attachments
    attachments = ResearchAttachment.query.filter_by(
        project_id=project.id, step_index=step_index
    ).all()
    if attachments:
        lines.append("\n## Attachments\n")
        for att in attachments:
            lines.append(f"- [{att.title}](attachments/{att.original_filename})")

    return "\n".join(lines)


def _build_decision_file(project):
    """Build the decision.md file"""
    if not project.decision:
        return None

    lines = []
    lines.append("# Investment Decision")
    lines.append(f"**Decision:** {project.decision.title()}")

    if project.decision_confidence:
        lines.append(f"**Confidence:** {project.decision_confidence}/10")
    if project.decision_date:
        lines.append(f"**Date:** {project.decision_date.strftime('%Y-%m-%d')}")

    if project.decision_notes:
        lines.append("\n## Decision Notes\n")
        lines.append(project.decision_notes)

    if project.too_hard_reason:
        lines.append("\n## Too Hard Reason\n")
        reason_labels = {
            'too_complex': 'Too complex to analyze',
            'insufficient_info': 'Insufficient public information',
            'outside_competence': 'Outside circle of competence',
            'better_opportunities': 'Better opportunities available',
            'other': 'Other',
        }
        lines.append(reason_labels.get(project.too_hard_reason, project.too_hard_reason))
        if project.too_hard_notes:
            lines.append(f"\n{project.too_hard_notes}")

    if project.green_flags:
        lines.append("\n## Green Flags\n")
        for flag in project.green_flags:
            lines.append(f"- {flag}")

    if project.red_flags:
        lines.append("\n## Red Flags\n")
        for flag in project.red_flags:
            lines.append(f"- {flag}")

    return "\n".join(lines)


@research_workflow_bp.route('/projects/<int:project_id>/export')
@login_required
def export_project(project_id):
    """Export the entire research project as a ZIP archive"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        abort(403)

    company_name = _safe_name(project.company.name if project.company else 'Unknown')
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    folder_name = f"{company_name}_Research_{date_str}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # README
        zf.writestr(f"{folder_name}/00_README.md", _build_readme(project))

        # Step files
        if project.template and project.template.workflow_steps:
            for i, step in enumerate(project.template.workflow_steps):
                step_name = _safe_name(step.get('name', f'Step_{i+1}'))
                filename = f"{folder_name}/{i+1:02d}_{step_name}.md"
                zf.writestr(filename, _build_step_file(project, i, step))

        # Decision file
        decision_md = _build_decision_file(project)
        if decision_md:
            zf.writestr(f"{folder_name}/decision.md", decision_md)

        # PDF report
        try:
            pdf_bytes = generate_pdf_report(project)
            zf.writestr(f"{folder_name}/Research_Report.pdf", pdf_bytes)
        except Exception:
            logger.warning("PDF report generation failed, skipping", exc_info=True)

        # Attachments
        all_attachments = ResearchAttachment.query.filter_by(project_id=project.id).all()
        for att in all_attachments:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.stored_filename)
            if os.path.exists(file_path):
                zf.write(file_path, f"{folder_name}/attachments/{att.original_filename}")

    buf.seek(0)
    zip_filename = f"{folder_name}.zip"

    return Response(
        buf.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    )
