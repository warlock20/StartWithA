"""
Generic Export Service
Reusable markdown builders and ZIP assemblers for exporting research projects
and company journey data.
"""

import io
import json
import logging
import os
import zipfile

from app.utils.blocknote_utils import blocknote_to_text
from app.utils.time_utils import now_utc
from app.models import (
    ResearchProject, CompanyResource,
    FreeResearchQuestion, ChecklistAnalysis, ChecklistAnswer,
    ThesisEvolution, DestinationCheckpoint,
    Transaction, DecisionJournal, JournalEntry,
)
from app.utils.checklist_utils import get_all_ordered_items_for_checklist

logger = logging.getLogger(__name__)

# ── Shared constants ────────────────────────────────────────────────────────

STATUS_LABELS = {
    'satisfied': 'Satisfied',
    'neutral': 'Neutral',
    'concerned': 'Concerned',
    'not_set': 'Not Set',
}

_TOO_HARD_LABELS = {
    'too_complex': 'Too complex to analyze',
    'insufficient_info': 'Insufficient public information',
    'outside_competence': 'Outside circle of competence',
    'better_opportunities': 'Better opportunities available',
    'other': 'Other',
}


# ── Shared utilities ────────────────────────────────────────────────────────

def safe_name(text):
    """Convert text to a safe filename component."""
    return "".join(
        c if c.isalnum() or c in (' ', '-', '_') else '_'
        for c in (text or 'Unknown')
    ).strip()


def blocknote_to_markdown(content):
    """
    Convert BlockNote JSON content into lightweight markdown preserving
    headings, paragraphs, lists, and inline formatting.  Falls back to
    plain text when the content is not valid BlockNote JSON.
    """
    if not content or not str(content).strip():
        return ''

    try:
        blocks = json.loads(content)
        if not isinstance(blocks, list):
            return blocknote_to_text(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return blocknote_to_text(content)

    parts = []
    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get('type', '')
        content_list = block.get('content', [])
        props = block.get('props', {}) or {}

        text = ''
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict) and item.get('type') == 'text':
                    t = item.get('text', '') or ''
                    styles = item.get('styles', {}) or {}
                    if styles.get('bold'):
                        t = f"**{t}**"
                    if styles.get('italic'):
                        t = f"*{t}*"
                    if styles.get('strike'):
                        t = f"~~{t}~~"
                    text += t

        if not text.strip() and block_type not in ('bulletListItem', 'numberedListItem'):
            parts.append('')
            continue

        if block_type == 'heading':
            level = props.get('level', 2)
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 2
            level = max(1, min(level, 6))
            parts.append(f"{'#' * level} {text}")
        elif block_type == 'bulletListItem':
            parts.append(f"- {text}")
        elif block_type == 'numberedListItem':
            parts.append(f"1. {text}")
        elif block_type == 'quote':
            parts.append(f"> {text}")
        else:
            parts.append(text)

    return "\n".join(parts).strip()


def format_dt(dt):
    """Format a datetime as YYYY-MM-DD HH:MM, or empty string if None."""
    if not dt:
        return ''
    try:
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(dt)


def _format_date(d):
    """Format a date (not datetime) as YYYY-MM-DD, or empty string if None."""
    if not d:
        return ''
    try:
        return d.strftime('%Y-%m-%d')
    except Exception:
        return str(d)


def _table_cell(text):
    """Escape a string for use inside a markdown table cell."""
    return str(text or '').replace('|', '\\|').replace('\n', ' ').strip()


def resolve_checklist_id(project, step_index, step):
    """
    Resolve the checklist_id for a checklist step, checking step_overrides
    first (runtime user selection) then falling back to template config.
    """
    checklist_id = None
    if project.step_overrides and str(step_index) in (project.step_overrides or {}):
        checklist_id = project.step_overrides[str(step_index)].get('checklist_id')
    if not checklist_id:
        checklist_id = step.get('config', {}).get('checklist_id')
    return int(checklist_id) if checklist_id else None


# ── Checklist analysis builder ──────────────────────────────────────────────

def build_checklist_analysis_section(analysis, heading_level=2):
    """
    Build a detailed markdown section for a single ChecklistAnalysis including
    metadata, conclusion, completion statistics, and every item with its
    answer rendered in hierarchical order.
    """
    if not analysis:
        return ''

    h = '#' * max(1, min(heading_level, 6))
    sub_h = '#' * max(1, min(heading_level + 1, 6))
    lines = []

    checklist_name = (
        analysis.checklist.name
        if analysis.checklist
        else f"Checklist #{analysis.checklist_id}"
    )
    lines.append(f"{h} {checklist_name}")
    lines.append("")
    lines.append(f"- **Analysis ID:** {analysis.id}")
    lines.append(f"- **Status:** {(analysis.status or 'unknown').replace('_', ' ').title()}")
    if analysis.start_date:
        lines.append(f"- **Started:** {format_dt(analysis.start_date)}")

    # Pull answers + items for stats
    answers = ChecklistAnswer.query.filter_by(
        checklist_analysis_id=analysis.id
    ).all()
    answers_map = {a.checklist_item_id: a for a in answers}
    all_items = get_all_ordered_items_for_checklist(analysis.checklist_id) or []

    total = len(all_items)
    answered = sum(1 for it in all_items if it.id in answers_map)
    status_counts = {'satisfied': 0, 'neutral': 0, 'concerned': 0, 'not_set': 0}
    for it in all_items:
        a = answers_map.get(it.id)
        if a:
            key = (a.satisfaction_status or 'not_set').strip() or 'not_set'
            status_counts[key] = status_counts.get(key, 0) + 1

    completion_pct = round((answered / total) * 100, 1) if total else 0
    lines.append(f"- **Completion:** {answered} of {total} items answered ({completion_pct}%)")
    lines.append(
        f"- **Breakdown:** "
        f"Satisfied {status_counts.get('satisfied', 0)} | "
        f"Neutral {status_counts.get('neutral', 0)} | "
        f"Concerned {status_counts.get('concerned', 0)} | "
        f"Not Set {status_counts.get('not_set', 0)}"
    )
    lines.append("")

    if analysis.conclusion:
        conclusion_md = blocknote_to_markdown(analysis.conclusion)
        if conclusion_md:
            lines.append(f"{sub_h} Overall Conclusion")
            lines.append("")
            lines.append(conclusion_md)
            lines.append("")

    if not all_items:
        lines.append("_This checklist has no items defined._")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"{sub_h} Item-by-Item Responses")
    lines.append("")

    item_map = {it.id: it for it in all_items}

    def depth_of(item_id):
        d = 0
        cur = item_map.get(item_id)
        while cur and cur.parent_id and cur.parent_id in item_map:
            d += 1
            cur = item_map[cur.parent_id]
        return d

    for it in all_items:
        d = depth_of(it.id)
        indent = '  ' * d
        lines.append(f"{indent}- **{it.text}**")

        if it.description:
            desc = str(it.description).strip()
            for dline in desc.splitlines() or [desc]:
                lines.append(f"{indent}  > {dline}")

        answer = answers_map.get(it.id)
        if answer:
            status_key = (answer.satisfaction_status or 'not_set').strip() or 'not_set'
            status_label = STATUS_LABELS.get(
                status_key, status_key.replace('_', ' ').title()
            )
            lines.append(f"{indent}  - Status: **{status_label}**")
            if answer.answered_at:
                lines.append(f"{indent}  - Answered: {format_dt(answer.answered_at)}")
            if answer.answer_text:
                answer_md = blocknote_to_markdown(answer.answer_text)
                if answer_md:
                    lines.append(f"{indent}  - Answer:")
                    lines.append("")
                    for aline in answer_md.splitlines():
                        lines.append(f"{indent}    {aline}" if aline else "")
                    lines.append("")
                else:
                    lines.append(f"{indent}  - Answer: _(empty)_")
            else:
                lines.append(f"{indent}  - Answer: _(no text provided)_")
        else:
            lines.append(f"{indent}  - Status: _Not answered_")

        lines.append("")

    return "\n".join(lines)


# ── Research project builders ───────────────────────────────────────────────

def build_research_readme(project):
    """Build the README.md overview file for a research project."""
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
        lines.append(blocknote_to_markdown(project.investment_thesis))

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


def build_research_step_file(project, step_index, step):
    """Build a markdown file for a single research workflow step."""
    lines = []
    lines.append(f"# Step {step_index + 1}: {step['name']}")
    lines.append(f"**Type:** {step.get('type', 'research').replace('_', ' ').title()}")

    time_spent = (project.time_per_step or {}).get(str(step_index), 0)
    if time_spent:
        lines.append(f"**Time Spent:** {round(time_spent)} minutes")

    is_completed = step_index in (project.completed_steps or [])
    lines.append(f"**Status:** {'Completed' if is_completed else 'Not completed'}")

    # Step notes — use blocknote_to_markdown for richer output
    notes = (project.step_notes or {}).get(str(step_index), '')
    if notes and notes != '[SKIPPED]':
        lines.append("\n## Notes\n")
        text = blocknote_to_markdown(notes) if notes.startswith('[') else notes
        lines.append(text if text else notes)
    elif notes == '[SKIPPED]':
        lines.append("\n*This step was skipped.*")

    # Free research questions — use blocknote_to_markdown
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
                    answer_md = blocknote_to_markdown(q.answer_content)
                    if answer_md:
                        lines.append(answer_md)
                lines.append("")

    # Checklist answers — delegate to the detailed builder
    if step.get('type') == 'checklist' and project.company_id:
        checklist_id = resolve_checklist_id(project, step_index, step)
        if checklist_id:
            analysis = ChecklistAnalysis.query.filter_by(
                user_id=project.user_id,
                checklist_id=checklist_id,
                company_id=project.company_id
            ).order_by(ChecklistAnalysis.start_date.desc()).first()

            if analysis:
                lines.append("")
                lines.append(build_checklist_analysis_section(analysis, heading_level=2))
            else:
                lines.append("\n## Checklist Answers\n")
                lines.append("_No checklist analysis found for this company._")

    # Step resources (files attached during this research step)
    attachments = CompanyResource.query.filter_by(
        research_project_id=project.id, research_step_index=step_index, resource_type='file'
    ).all()
    if attachments:
        lines.append("\n## Attachments\n")
        for att in attachments:
            lines.append(f"- [{att.title}](attachments/{att.original_filename})")

    return "\n".join(lines)


def build_research_decision_file(project):
    """Build the decision.md file for a research project."""
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
        lines.append(blocknote_to_markdown(project.decision_notes))

    if project.too_hard_reason:
        lines.append("\n## Too Hard Reason\n")
        lines.append(_TOO_HARD_LABELS.get(project.too_hard_reason, project.too_hard_reason))
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


# ── Company journey builders ────────────────────────────────────────────────

def build_thesis_evolution_md(thesis_versions, company_name):
    """Build markdown for all thesis evolution versions."""
    if not thesis_versions:
        return None

    lines = [f"# Thesis Evolution — {company_name}", ""]
    sorted_versions = sorted(thesis_versions, key=lambda t: t.version or 0)

    for tv in sorted_versions:
        current_tag = " (Current)" if tv.is_current else ""
        date_str = format_dt(tv.created_at) if tv.created_at else "Unknown date"
        lines.append(f"## Version {tv.version}{current_tag} — {date_str}")
        lines.append("")

        if tv.conviction_level:
            lines.append(f"**Conviction:** {tv.conviction_level}/10")
        if tv.position_sizing:
            lines.append(f"**Position Sizing:** {tv.position_sizing.replace('_', ' ').title()}")
        if tv.change_trigger:
            lines.append(f"**Change Trigger:** {tv.change_trigger}")
        lines.append("")

        if tv.change_summary:
            lines.append("### Change Summary")
            lines.append("")
            lines.append(tv.change_summary)
            lines.append("")

        if tv.thesis:
            lines.append("### Thesis")
            lines.append("")
            lines.append(blocknote_to_markdown(tv.thesis))
            lines.append("")

        if tv.bull_case:
            lines.append("### Bull Case")
            lines.append("")
            for point in tv.bull_case:
                lines.append(f"- {point}")
            lines.append("")

        if tv.bear_case:
            lines.append("### Bear Case")
            lines.append("")
            for point in tv.bear_case:
                lines.append(f"- {point}")
            lines.append("")

        if tv.key_metrics:
            lines.append("### Key Metrics")
            lines.append("")
            if isinstance(tv.key_metrics, dict):
                for k, v in tv.key_metrics.items():
                    lines.append(f"- **{k}:** {v}")
            elif isinstance(tv.key_metrics, list):
                for m in tv.key_metrics:
                    lines.append(f"- {m}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_checkpoints_md(checkpoints, company_name):
    """Build markdown for destination checkpoints."""
    if not checkpoints:
        return None

    lines = [f"# Destination Checkpoints — {company_name}", ""]

    # Summary table
    lines.append("| Target Date | Metric | Expectation | Status |")
    lines.append("|------------|--------|-------------|--------|")
    for cp in checkpoints:
        date_str = _format_date(cp.target_date)
        lines.append(f"| {date_str} | {_table_cell(cp.metric)} | {_table_cell(cp.expectation)} | {_table_cell(cp.status)} |")
    lines.append("")

    # Detailed sections
    lines.append("## Checkpoint Details")
    lines.append("")

    for cp in checkpoints:
        date_str = _format_date(cp.target_date)
        lines.append(f"### {cp.metric} — Target: {date_str}")
        lines.append("")
        lines.append(f"- **Status:** {cp.status}")
        lines.append(f"- **Expected:** {cp.expectation}")
        if cp.description:
            lines.append(f"- **Description:** {cp.description}")
        if cp.outcome_notes:
            lines.append(f"- **Outcome Notes:** {cp.outcome_notes}")
        lines.append("")

    return "\n".join(lines)


def build_transactions_md(transactions, company_name):
    """Build markdown for portfolio transactions."""
    if not transactions:
        return None

    company_txns = [t for t in transactions if t.type not in ('DEPOSIT', 'WITHDRAWAL')]
    if not company_txns:
        return None

    lines = [f"# Transaction History — {company_name}", ""]

    lines.append("| Date | Type | Qty | Price/Share | Fees | Currency | Notes |")
    lines.append("|------|------|-----|------------|------|----------|-------|")

    total_invested = 0
    total_sold = 0

    for t in company_txns:
        date_str = _format_date(t.date)
        qty = t.quantity or ''
        price = f"{t.price_per_share:.2f}" if t.price_per_share else ''
        fees = f"{t.fees:.2f}" if t.fees else '0.00'
        notes = _table_cell(t.notes)[:60]
        lines.append(f"| {date_str} | {t.type} | {qty} | {price} | {fees} | {t.currency} | {notes} |")

        if t.type == 'BUY' and t.price_per_share and t.quantity:
            total_invested += float(t.price_per_share) * t.quantity + float(t.fees or 0)
        elif t.type == 'SELL' and t.price_per_share and t.quantity:
            total_sold += float(t.price_per_share) * t.quantity - float(t.fees or 0)

    lines.append("")
    if total_invested:
        lines.append(f"**Total Invested:** {total_invested:,.2f}")
    if total_sold:
        lines.append(f"**Total Sold:** {total_sold:,.2f}")
    lines.append("")

    return "\n".join(lines)


def build_decision_journals_md(journals, company_name):
    """Build markdown for decision journal entries."""
    if not journals:
        return None

    lines = [f"# Decision Journal — {company_name}", ""]

    for dj in journals:
        type_label = (dj.decision_type or 'unknown').replace('_', ' ').title()
        date_str = _format_date(dj.decision_date)
        lines.append(f"## {type_label} Decision — {date_str}")
        lines.append("")

        if dj.confidence_score:
            lines.append(f"**Confidence:** {dj.confidence_score}/10")
        if dj.expected_return:
            lines.append(f"**Expected Return:** {dj.expected_return}%")
        if dj.expected_timeframe:
            lines.append(f"**Expected Timeframe:** {dj.expected_timeframe} months")
        lines.append("")

        if dj.investment_thesis:
            lines.append("### Investment Thesis")
            lines.append("")
            lines.append(blocknote_to_markdown(dj.investment_thesis))
            lines.append("")

        if dj.key_assumptions:
            lines.append("### Key Assumptions")
            lines.append("")
            for assumption in dj.key_assumptions:
                lines.append(f"- {assumption}")
            lines.append("")

        if dj.biggest_risks:
            lines.append("### Biggest Risks")
            lines.append("")
            for risk in dj.biggest_risks:
                lines.append(f"- {risk}")
            lines.append("")

        if dj.exit_criteria:
            lines.append("### Exit Criteria")
            lines.append("")
            lines.append(dj.exit_criteria)
            lines.append("")

        # Post-mortem / outcome section
        has_outcome = dj.actual_return is not None or dj.outcome_notes or dj.what_went_right
        if has_outcome:
            lines.append("### Outcome")
            lines.append("")
            if dj.actual_return is not None:
                lines.append(f"- **Actual Return:** {dj.actual_return}%")
            if dj.actual_timeframe:
                lines.append(f"- **Actual Timeframe:** {dj.actual_timeframe} months")
            if dj.outcome_date:
                lines.append(f"- **Outcome Date:** {_format_date(dj.outcome_date)}")
            if dj.outcome_notes:
                lines.append(f"- **Notes:** {dj.outcome_notes}")
            if dj.what_went_right:
                lines.append(f"- **What Went Right:** {dj.what_went_right}")
            if dj.what_went_wrong:
                lines.append(f"- **What Went Wrong:** {dj.what_went_wrong}")
            if dj.lessons_learned:
                lines.append(f"- **Lessons Learned:** {dj.lessons_learned}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_journal_entries_md(entries, company_name):
    """Build markdown for journal entries."""
    if not entries:
        return None

    lines = [f"# Journal Entries — {company_name}", ""]

    for entry in entries:
        date_str = format_dt(entry.created_at)
        title = entry.title or "Untitled Entry"
        lines.append(f"## {title} — {date_str}")
        lines.append("")

        meta_parts = []
        if entry.entry_type:
            meta_parts.append(f"**Type:** {entry.entry_type.replace('_', ' ').title()}")
        if entry.sentiment:
            meta_parts.append(f"**Sentiment:** {entry.sentiment.replace('_', ' ').title()}")
        if entry.conviction_level:
            meta_parts.append(f"**Conviction:** {entry.conviction_level}/10")
        if meta_parts:
            lines.append(" | ".join(meta_parts))
            lines.append("")

        if entry.content:
            lines.append(blocknote_to_markdown(entry.content))
            lines.append("")

        if entry.key_insight:
            lines.append(f"**Key Insight:** {entry.key_insight}")
            lines.append("")

        if entry.action_items:
            lines.append("**Action Items:**")
            lines.append("")
            for item in entry.action_items:
                lines.append(f"- {item}")
            lines.append("")

        if entry.tags:
            tags_str = " ".join(f"#{t}" for t in entry.tags)
            lines.append(f"**Tags:** {tags_str}")
            lines.append("")

        if entry.source:
            source_str = entry.source
            if entry.source_url:
                source_str = f"[{entry.source}]({entry.source_url})"
            lines.append(f"**Source:** {source_str}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_journey_notes_md(journey_notes, company_name):
    """Build markdown from company journey notes (BlockNote JSON)."""
    if not journey_notes:
        return None

    md = blocknote_to_markdown(journey_notes)
    if not md:
        return None

    return f"# Company Notes — {company_name}\n\n{md}\n"


def build_journey_overview_md(company, company_state, counts):
    """
    Build the README/overview file for a journey export.

    counts is a dict with keys:
        thesis, checkpoints, transactions, decisions, journal, research
    """
    lines = []
    lines.append(f"# Company Journey: {company.name}")
    if company.ticker_symbol:
        lines.append(f"**Ticker:** {company.ticker_symbol}")
    if company.sector:
        lines.append(f"**Sector:** {company.sector.name}")
    lines.append(f"**State:** {company_state.replace('_', ' ').title()}")
    lines.append(f"**Export Date:** {now_utc().strftime('%Y-%m-%d')}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Thesis Updates: {counts.get('thesis', 0)}")
    lines.append(f"- Checkpoints: {counts.get('checkpoints', 0)}")
    if company_state == 'portfolio':
        lines.append(f"- Transactions: {counts.get('transactions', 0)}")
    lines.append(f"- Decisions: {counts.get('decisions', 0)}")
    lines.append(f"- Journal Entries: {counts.get('journal', 0)}")
    if counts.get('research'):
        lines.append("- Research Project: Yes")
    lines.append("")

    return "\n".join(lines)


# ── ZIP assemblers ──────────────────────────────────────────────────────────

def export_research_project(project, upload_folder, pdf_bytes=None):
    """
    Build a ZIP archive for a research project.

    Args:
        project: ResearchProject instance
        upload_folder: Path to UPLOAD_FOLDER config
        pdf_bytes: Optional pre-generated PDF report bytes

    Returns:
        bytes: ZIP file content
    """
    company_name = safe_name(project.company.name if project.company else 'Unknown')
    date_str = now_utc().strftime('%Y-%m-%d')
    folder_name = f"{company_name}_Research_{date_str}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{folder_name}/00_README.md", build_research_readme(project))

        if project.template and project.template.workflow_steps:
            for i, step in enumerate(project.template.workflow_steps):
                step_name = safe_name(step.get('name', f'Step_{i+1}'))
                filename = f"{folder_name}/{i+1:02d}_{step_name}.md"
                zf.writestr(filename, build_research_step_file(project, i, step))

        decision_md = build_research_decision_file(project)
        if decision_md:
            zf.writestr(f"{folder_name}/decision.md", decision_md)

        if pdf_bytes:
            zf.writestr(f"{folder_name}/Research_Report.pdf", pdf_bytes)

        all_attachments = CompanyResource.query.filter_by(
            research_project_id=project.id, resource_type='file'
        ).all()
        for att in all_attachments:
            file_path = os.path.join(upload_folder, att.stored_filename)
            if os.path.exists(file_path):
                zf.write(file_path, f"{folder_name}/attachments/{att.original_filename}")

    buf.seek(0)
    return buf.getvalue()


def export_company_journey(company, user_id, components, company_state):
    """
    Build a ZIP archive for a company journey export.

    Args:
        company: Company instance
        user_id: Current user ID
        components: list of component keys to include:
            'thesis', 'checkpoints', 'transactions', 'decisions',
            'journal', 'notes', 'research'
        company_state: 'portfolio', 'watchlist', or 'new'

    Returns:
        bytes: ZIP file content
    """
    company_name = safe_name(company.name)
    date_str = now_utc().strftime('%Y-%m-%d')
    folder_name = f"{company_name}_Journey_{date_str}"

    buf = io.BytesIO()
    counts = {}
    file_index = 1

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        if 'thesis' in components:
            thesis_versions = ThesisEvolution.query.filter_by(
                company_id=company.id, user_id=user_id
            ).order_by(ThesisEvolution.created_at).all()
            counts['thesis'] = len(thesis_versions)
            md = build_thesis_evolution_md(thesis_versions, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_thesis_evolution.md", md)
                file_index += 1

        if 'checkpoints' in components:
            checkpoints = DestinationCheckpoint.query.filter_by(
                company_id=company.id, user_id=user_id
            ).order_by(DestinationCheckpoint.target_date).all()
            counts['checkpoints'] = len(checkpoints)
            md = build_checkpoints_md(checkpoints, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_checkpoints.md", md)
                file_index += 1

        if 'transactions' in components and company_state == 'portfolio':
            transactions = Transaction.query.filter_by(
                company_id=company.id, user_id=user_id
            ).order_by(Transaction.date).all()
            counts['transactions'] = len(transactions)
            md = build_transactions_md(transactions, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_transactions.md", md)
                file_index += 1

        if 'decisions' in components:
            decision_journals = DecisionJournal.query.filter_by(
                company_id=company.id, user_id=user_id
            ).order_by(DecisionJournal.decision_date).all()
            counts['decisions'] = len(decision_journals)
            md = build_decision_journals_md(decision_journals, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_decisions.md", md)
                file_index += 1

        if 'journal' in components:
            entries = JournalEntry.query.filter_by(
                company_id=company.id, user_id=user_id
            ).order_by(JournalEntry.created_at).all()
            counts['journal'] = len(entries)
            md = build_journal_entries_md(entries, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_journal_entries.md", md)
                file_index += 1

        if 'notes' in components:
            md = build_journey_notes_md(company.journey_notes, company.name)
            if md:
                zf.writestr(f"{folder_name}/{file_index:02d}_company_notes.md", md)
                file_index += 1

        if 'research' in components:
            project = ResearchProject.query.filter_by(
                company_id=company.id, user_id=user_id
            ).first()
            counts['research'] = 1 if project else 0
            if project:
                prefix = f"{folder_name}/{file_index:02d}_research"
                zf.writestr(
                    f"{prefix}/00_README.md",
                    build_research_readme(project)
                )
                if project.template and project.template.workflow_steps:
                    for i, step in enumerate(project.template.workflow_steps):
                        step_name = safe_name(step.get('name', f'Step_{i+1}'))
                        zf.writestr(
                            f"{prefix}/{i+1:02d}_{step_name}.md",
                            build_research_step_file(project, i, step)
                        )
                decision_md = build_research_decision_file(project)
                if decision_md:
                    zf.writestr(f"{prefix}/decision.md", decision_md)

        # Overview as the root README (always included)
        overview = build_journey_overview_md(company, company_state, counts)
        zf.writestr(f"{folder_name}/00_README.md", overview)

    buf.seek(0)
    return buf.getvalue()
