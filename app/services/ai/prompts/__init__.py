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
