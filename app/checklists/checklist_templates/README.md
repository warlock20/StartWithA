# Investment Checklist Templates

This directory contains YAML template files for investment checklists. Users can also upload their own custom templates.

## Template Format

Each template should be a YAML file with the following structure:

```yaml
# Template metadata
name: Template Name
description: Brief description of the template
category: general|financial|investing_style|risk|custom
difficulty: beginner|intermediate|advanced
estimated_time: X-Y hours
icon: 📊 (optional emoji)

# Checklist items
items:
  - text: Main Item Title
    llm_prompt: AI prompt for analyzing this item (optional)
    subitems:
      - text: Subitem text
        llm_prompt: AI prompt for this subitem (optional)
      - text: Another subitem
        llm_prompt: Another AI prompt

  - text: Another Main Item
    llm_prompt: Prompt for this item
    subitems:
      - text: Subitem
        llm_prompt: Prompt
```

## Template Categories

- **general**: Broad investment analysis templates
- **financial**: Financial statement and metrics analysis
- **investing_style**: Templates for specific investment philosophies (value, growth, etc.)
- **risk**: Risk assessment and due diligence templates
- **custom**: User-uploaded custom templates

## Built-in Templates

1. **basic_analysis.yaml** - Comprehensive starting point for any investment
2. **value_investing.yaml** - Graham/Buffett-style value investing framework
3. **growth_investing.yaml** - High-growth company evaluation
4. **financial_deep_dive.yaml** - Detailed financial analysis (coming soon)
5. **risk_assessment.yaml** - Risk evaluation framework (coming soon)
6. **competitive_analysis.yaml** - Competitive position analysis (coming soon)

## Adding Custom Templates

Users can:
1. Upload YAML files through the web interface
2. Export existing checklists as YAML for reuse
3. Modify existing templates and save as new templates

## LLM Prompts

The `llm_prompt` field is optional but recommended. It helps AI-powered analysis by providing specific instructions for what to look for. Good prompts are:
- Specific and actionable
- Focused on analysis and insights
- Aligned with the item's question

Example:
```yaml
- text: What is the company's competitive advantage?
  llm_prompt: Analyze the company's unique value proposition and identify sustainable competitive moats using Porter's framework
```
