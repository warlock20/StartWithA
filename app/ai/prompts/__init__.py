"""AI Prompt Templates

All prompts are now managed via YAML files for easy tuning and version control.
Use PromptService to load and format prompts.

Example:
    from app.ai.services.prompt_service import get_sector_research_prompt

    prompt = get_sector_research_prompt(
        'section_summaries',
        sector_name='Technology',
        bullet_count=7,
        research_content='...',
        focus_guideline=''
    )
"""
