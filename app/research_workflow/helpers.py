from flask_login import current_user
from app.models import ResearchSession, ResearchAnswer


def collect_research_session_summary(project, step_index):
    """
    Collect and summarize the actual research data from the completed research session
    """
    try:
        # Find the most recent research session for this project's company

        if not project.company_id:
            return "Completed research checklist evaluation (no company data)"

        # Get the most recent research session for this company (check all statuses first)
        all_sessions = ResearchSession.query.filter_by(
            user_id=current_user.id,
            company_id=project.company_id
        ).order_by(ResearchSession.start_date.desc()).all()


        # Get the most recent research session for this company (try 'completed' first)
        recent_session = ResearchSession.query.filter_by(
            user_id=current_user.id,
            company_id=project.company_id,
            status='completed'
        ).order_by(ResearchSession.start_date.desc()).first()

        # If no completed session, try any recent session
        if not recent_session and all_sessions:
            recent_session = all_sessions[0]

        if not recent_session:
            return "Completed research checklist evaluation (no research session found)"

        # Collect all research answers from the session
        research_answers = ResearchAnswer.query.filter_by(
            research_session_id=recent_session.id
        ).all()

        if not research_answers:
            return f"Completed research evaluation using {recent_session.checklist.name} (no answers recorded)"

        # Build summary from the research answers
        summary_parts = [
            f"**Research Summary: {recent_session.checklist.name}**",
            f"Company: {project.company.name} ({project.company.ticker_symbol})",
            f"Completed: {recent_session.start_date.strftime('%Y-%m-%d')}",
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

        final_summary = "\n".join(summary_parts)
        return final_summary

    except Exception as e:
        import traceback
        print(f"ERROR in collect_research_session_summary: {e}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        return f"Completed research checklist evaluation (error collecting details: {str(e)})"
