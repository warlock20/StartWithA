"""
AI Prompt Templates

All prompts are managed via YAML files for easy tuning and version control.
Use PromptService to load and format prompts.

Directory Structure:
    prompts/
    ├── kill_checklist/          # Kill checklist related prompts
    │   ├── mistake_analysis.yaml
    │   └── effectiveness_scoring.yaml
    ├── research_journal/        # Research journal prompts
    │   ├── entry_analysis.yaml
    │   ├── thesis_contradiction_detection.yaml
    │   └── related_entries_finder.yaml
    ├── research_template/       # Research template prompts
    │   ├── step_optimization.yaml
    │   └── sector_question_matching.yaml
    ├── sector_research/         # Sector research prompts
    │   └── section_summaries.yaml
    └── document_processing/     # Document processing prompts
        ├── document_to_checklist_immediate.yaml
        └── document_to_checklist_interactive.yaml

Usage:
    from app.services.ai.prompt_service import prompt_service, get_research_journal_prompt

    # Using service directly
    prompt = prompt_service.get_prompt(
        'kill_checklist',
        'mistake_analysis',
        mistake_title="Bad investment",
        mistake_cost=25000
    )
    
    # Using convenience function
    prompt = get_research_journal_prompt(
        'entry_analysis',
        entry_title="Market Analysis",
        entry_content="...",
        company_name="Apple Inc"
    )
"""
