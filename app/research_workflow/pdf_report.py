"""
PDF Report Generator for Research Projects.
Uses PyMuPDF (fitz) Story API to render HTML/CSS to PDF.
"""

import io
import re
import fitz
import logging
from datetime import datetime
from app.models import (ResearchAttachment, FreeResearchQuestion,
                        ChecklistAnalysis, ChecklistAnswer)
from app.utils.blocknote_utils import blocknote_to_html, blocknote_to_text
from app.research_workflow.checklist_check_routes import get_all_ordered_items_for_checklist

logger = logging.getLogger(__name__)

# Letter paper dimensions in points
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_LEFT = 72
MARGIN_RIGHT = 540
MARGIN_TOP = 90
MARGIN_BOTTOM = 720

REPORT_CSS = """
body {
    font-family: Helvetica, sans-serif;
    font-size: 10pt;
    color: #333333;
    line-height: 1.6;
}
h1 {
    font-size: 22pt;
    color: #1a1a2e;
    border-bottom: 2px solid #16213e;
    padding-bottom: 6pt;
    margin-bottom: 4pt;
}
h2 {
    font-size: 14pt;
    color: #16213e;
    margin-top: 16pt;
    margin-bottom: 6pt;
    border-bottom: 1px solid #cccccc;
    padding-bottom: 3pt;
}
h3 {
    font-size: 11pt;
    color: #0f3460;
    margin-top: 10pt;
    margin-bottom: 4pt;
}
h4 {
    font-size: 10pt;
    color: #333333;
    margin-top: 8pt;
    margin-bottom: 2pt;
}
p {
    margin-top: 2pt;
    margin-bottom: 4pt;
}
.meta {
    color: #666666;
    font-size: 9pt;
    margin-bottom: 14pt;
}
.flag-green {
    color: #2d6a4f;
    background-color: #d8f3dc;
    padding: 3pt 6pt;
    margin: 2pt 0;
}
.flag-red {
    color: #9d0208;
    background-color: #fde2e4;
    padding: 3pt 6pt;
    margin: 2pt 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 6pt 0;
}
th {
    background-color: #e2e8f0;
    padding: 5pt 6pt;
    text-align: left;
    font-size: 9pt;
    font-weight: bold;
}
td {
    padding: 4pt 6pt;
    border-bottom: 1px solid #e2e8f0;
    font-size: 9pt;
}
.skipped {
    color: #999999;
    font-style: italic;
}
.page-break {
    page-break-before: always;
}
.step-meta {
    color: #666666;
    font-size: 9pt;
    margin-bottom: 6pt;
}
li {
    margin-bottom: 2pt;
}
"""


def _esc(text):
    """Escape HTML special characters."""
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _md_to_html(text):
    """Convert simple markdown (bold, newlines) to HTML."""
    if not text:
        return ''
    text = _esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = text.replace('\n', '<br/>')
    return text


def _build_title_html(project):
    company = project.company
    company_name = _esc(company.name) if company else 'Unknown Company'
    ticker = f" ({_esc(company.ticker_symbol)})" if company and company.ticker_symbol else ''

    sector_name = ''
    if project.sector:
        sector_name = project.sector.display_name
    elif company and company.sector:
        sector_name = company.sector.display_name

    template_name = _esc(project.template.name) if project.template else 'Unknown'
    date_str = datetime.utcnow().strftime('%B %d, %Y')

    parts = [f'<h1>{company_name}{ticker}</h1>']
    parts.append('<p class="meta">')
    if sector_name:
        parts.append(f'{_esc(sector_name)} &middot; ')
    parts.append(f'Template: {template_name}<br/>')
    parts.append(f'Report generated: {date_str}')
    parts.append('</p>')
    return '\n'.join(parts)


def _build_overview_html(project):
    parts = ['<h2>Project Overview</h2>', '<table>']

    status = _esc((project.status or 'unknown').title())
    parts.append(f'<tr><td><strong>Status</strong></td><td>{status}</td></tr>')

    if project.decision:
        parts.append(f'<tr><td><strong>Decision</strong></td><td>{_esc(project.decision.title())}</td></tr>')
    if project.decision_confidence:
        parts.append(f'<tr><td><strong>Confidence</strong></td><td>{project.decision_confidence}/10</td></tr>')
    if project.decision_date:
        parts.append(f'<tr><td><strong>Decision Date</strong></td><td>{project.decision_date.strftime("%Y-%m-%d")}</td></tr>')

    hours = round(project.total_hours_spent or 0, 1)
    parts.append(f'<tr><td><strong>Time Invested</strong></td><td>{hours} hours</td></tr>')

    completed = len(project.completed_steps or [])
    total = project.template.step_count if project.template else 0
    parts.append(f'<tr><td><strong>Steps Completed</strong></td><td>{completed} of {total}</td></tr>')

    if project.last_worked_at:
        parts.append(f'<tr><td><strong>Last Worked</strong></td><td>{project.last_worked_at.strftime("%Y-%m-%d")}</td></tr>')

    parts.append('</table>')
    return '\n'.join(parts)


def _build_thesis_html(project):
    if not project.investment_thesis:
        return ''
    return f'<h2>Investment Thesis</h2>\n<p>{_md_to_html(project.investment_thesis)}</p>'


def _build_flags_html(project):
    parts = []
    has_content = project.green_flags or project.red_flags or project.key_findings

    if not has_content:
        return ''

    if project.green_flags:
        parts.append('<h2>Green Flags</h2>')
        for flag in project.green_flags:
            parts.append(f'<p class="flag-green">{_esc(flag)}</p>')

    if project.red_flags:
        parts.append('<h2>Red Flags</h2>')
        for flag in project.red_flags:
            parts.append(f'<p class="flag-red">{_esc(flag)}</p>')

    if project.key_findings:
        parts.append('<h2>Key Findings</h2>')
        parts.append('<ul>')
        for finding in project.key_findings:
            parts.append(f'<li>{_esc(finding)}</li>')
        parts.append('</ul>')

    return '\n'.join(parts)


def _build_step_html(project, step_index, step):
    parts = []
    step_name = _esc(step.get('name', f'Step {step_index + 1}'))
    step_type = step.get('type', 'research').replace('_', ' ').title()

    parts.append(f'<h2>Step {step_index + 1}: {step_name}</h2>')

    meta_items = [f'Type: {_esc(step_type)}']
    time_spent = (project.time_per_step or {}).get(str(step_index), 0)
    if time_spent:
        meta_items.append(f'Time: {round(time_spent)} min')

    is_completed = step_index in (project.completed_steps or [])
    meta_items.append(f'Status: {"Completed" if is_completed else "Not completed"}')
    parts.append(f'<p class="step-meta">{" &middot; ".join(meta_items)}</p>')

    # Step notes
    notes = (project.step_notes or {}).get(str(step_index), '')
    if notes and notes != '[SKIPPED]':
        parts.append('<h3>Notes</h3>')
        if notes.strip().startswith('['):
            html = blocknote_to_html(notes)
            parts.append(html if html else f'<p>{_esc(notes)}</p>')
        else:
            parts.append(f'<p>{_md_to_html(notes)}</p>')
    elif notes == '[SKIPPED]':
        parts.append('<p class="skipped">This step was skipped.</p>')

    # Free research questions
    if step.get('type') == 'free_research':
        questions = FreeResearchQuestion.query.filter_by(
            project_id=project.id,
            step_index=step_index
        ).order_by(FreeResearchQuestion.order_index).all()

        if questions:
            parts.append('<h3>Research Questions</h3>')
            for i, q in enumerate(questions, 1):
                status = 'Answered' if q.status == 'answered' else 'Exploring'
                parts.append(f'<h4>Q{i}: {_esc(q.question_text)}</h4>')
                parts.append(f'<p class="step-meta">Status: {status}</p>')
                if q.answer_content:
                    answer_html = blocknote_to_html(q.answer_content)
                    if answer_html:
                        parts.append(answer_html)

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
                    parts.append('<h3>Checklist Answers</h3>')
                    parts.append('<table><tr><th>Item</th><th>Status</th><th>Answer</th></tr>')
                    for item in all_items:
                        answer = answers_map.get(item.id)
                        item_text = _esc(item.text)
                        if answer:
                            status = _esc((answer.satisfaction_status or 'not set').replace('_', ' ').title())
                            answer_text = ''
                            if answer.answer_text:
                                answer_text = _esc(blocknote_to_text(answer.answer_text))
                            parts.append(f'<tr><td>{item_text}</td><td>{status}</td><td>{answer_text}</td></tr>')
                        else:
                            parts.append(f'<tr><td>{item_text}</td><td>-</td><td>-</td></tr>')
                    parts.append('</table>')

    # Step attachments
    attachments = ResearchAttachment.query.filter_by(
        project_id=project.id, step_index=step_index
    ).all()
    if attachments:
        parts.append('<h3>Attachments</h3>')
        parts.append('<ul>')
        for att in attachments:
            parts.append(f'<li>{_esc(att.title)} ({_esc(att.original_filename)})</li>')
        parts.append('</ul>')

    return '\n'.join(parts)


def _build_decision_html(project):
    if not project.decision:
        return ''

    parts = ['<h2>Investment Decision</h2>']
    parts.append('<table>')
    parts.append(f'<tr><td><strong>Decision</strong></td><td>{_esc(project.decision.title())}</td></tr>')
    if project.decision_confidence:
        parts.append(f'<tr><td><strong>Confidence</strong></td><td>{project.decision_confidence}/10</td></tr>')
    if project.decision_date:
        parts.append(f'<tr><td><strong>Date</strong></td><td>{project.decision_date.strftime("%Y-%m-%d")}</td></tr>')
    parts.append('</table>')

    if project.decision_notes:
        parts.append('<h3>Decision Notes</h3>')
        parts.append(f'<p>{_md_to_html(project.decision_notes)}</p>')

    if project.too_hard_reason:
        reason_labels = {
            'too_complex': 'Too complex to analyze',
            'insufficient_info': 'Insufficient public information',
            'outside_competence': 'Outside circle of competence',
            'better_opportunities': 'Better opportunities available',
            'other': 'Other',
        }
        parts.append('<h3>Too Hard Reason</h3>')
        parts.append(f'<p>{_esc(reason_labels.get(project.too_hard_reason, project.too_hard_reason))}</p>')
        if project.too_hard_notes:
            parts.append(f'<p>{_md_to_html(project.too_hard_notes)}</p>')

    return '\n'.join(parts)


def _build_full_html(project):
    """Assemble all sections into a complete HTML document."""
    sections = [_build_title_html(project), _build_overview_html(project)]

    thesis = _build_thesis_html(project)
    if thesis:
        sections.append(thesis)

    flags = _build_flags_html(project)
    if flags:
        sections.append(flags)

    # Steps - each on a new page
    if project.template and project.template.workflow_steps:
        for i, step in enumerate(project.template.workflow_steps):
            step_html = _build_step_html(project, i, step)
            sections.append(f'<div class="page-break">{step_html}</div>')

    decision = _build_decision_html(project)
    if decision:
        sections.append(f'<div class="page-break">{decision}</div>')

    # Project-level attachments
    proj_attachments = ResearchAttachment.query.filter_by(
        project_id=project.id, step_index=None
    ).all()
    if proj_attachments:
        att_html = '<h2>Project Attachments</h2><ul>'
        for att in proj_attachments:
            att_html += f'<li>{_esc(att.title)} ({_esc(att.original_filename)}, {round(att.file_size / 1024)}KB)</li>'
        att_html += '</ul>'
        sections.append(att_html)

    return '\n'.join(sections)


def _add_headers_footers(doc, company_name):
    """Overlay header and footer on each page."""
    total_pages = doc.page_count
    header_text = f"{company_name}  \u2014  Research Report"

    for i in range(total_pages):
        page = doc[i]
        # Header text
        header_rect = fitz.Rect(MARGIN_LEFT, 25, MARGIN_RIGHT, 50)
        page.insert_textbox(
            header_rect, header_text,
            fontsize=8, color=(0.45, 0.45, 0.45),
            align=fitz.TEXT_ALIGN_LEFT
        )
        # Header rule
        page.draw_line(
            fitz.Point(MARGIN_LEFT, 58), fitz.Point(MARGIN_RIGHT, 58),
            color=(0.82, 0.82, 0.82), width=0.5
        )
        # Footer: page number
        footer_rect = fitz.Rect(MARGIN_LEFT, 740, MARGIN_RIGHT, 760)
        page.insert_textbox(
            footer_rect, f"Page {i + 1} of {total_pages}",
            fontsize=8, color=(0.5, 0.5, 0.5),
            align=fitz.TEXT_ALIGN_CENTER
        )


def generate_pdf_report(project):
    """
    Generate a PDF report for a research project.

    Returns:
        bytes: PDF file content
    """
    html_content = _build_full_html(project)
    company_name = project.company.name if project.company else 'Unknown'

    content_rect = fitz.Rect(MARGIN_LEFT, MARGIN_TOP, MARGIN_RIGHT, MARGIN_BOTTOM)

    # Pass 1: Render HTML to PDF pages via Story + DocumentWriter
    bio = io.BytesIO()
    writer = fitz.DocumentWriter(bio)
    story = fitz.Story(html_content, user_css=REPORT_CSS)

    more = True
    while more:
        dev = writer.begin_page(fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT))
        more, _ = story.place(content_rect)
        story.draw(dev)
        writer.end_page()

    writer.close()

    # Pass 2: Reopen to overlay headers and footers
    bio.seek(0)
    doc = fitz.open('pdf', bio.read())
    _add_headers_footers(doc, company_name)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
