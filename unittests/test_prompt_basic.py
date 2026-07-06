#!/usr/bin/env python3
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

"""Basic test of prompt management without Flask dependencies"""

import yaml
import os
from pathlib import Path

def test_basic_prompt_loading():
    """Test basic YAML loading and templating without Flask"""
    print("🧪 Basic Prompt Management Test")
    print("=" * 40)

    # Test YAML loading
    prompts_dir = Path(__file__).parent / "app" / "prompts" / "kill_checklist"

    if not prompts_dir.exists():
        print(f"❌ Prompts directory not found: {prompts_dir}")
        return False

    # Load the mistake analysis prompt
    mistake_prompt_file = prompts_dir / "mistake_analysis.yaml"

    if not mistake_prompt_file.exists():
        print(f"❌ Mistake analysis prompt not found: {mistake_prompt_file}")
        return False

    with open(mistake_prompt_file, 'r') as f:
        prompt_data = yaml.safe_load(f)

    print("✅ YAML loading works")
    print(f"   Prompt name: {prompt_data['name']}")
    print(f"   Description: {prompt_data['description']}")
    print(f"   Version: {prompt_data['version']}")

    # Test template rendering
    template = prompt_data['template']
    sample_vars = {
        'mistake_title': 'Test Mistake',
        'mistake_description': 'Test description',
        'mistake_type': 'analysis_error',
        'mistake_severity': 8,
        'mistake_cost': '$10,000',
        'mistake_date': '2024-01-01',
        'existing_criteria': 'No existing criteria'
    }

    try:
        rendered = template.format(**sample_vars)
        print("✅ Template rendering works")
        print(f"   Rendered length: {len(rendered)} characters")
        print(f"   Contains variables: {'✅' if 'Test Mistake' in rendered else '❌'}")
    except KeyError as e:
        print(f"❌ Template rendering failed: missing variable {e}")
        return False

    # Test system context
    if 'system_context' in prompt_data:
        system_context = prompt_data['system_context']
        print("✅ System context loaded")
        print(f"   Context length: {len(system_context)} characters")

    # Test output format
    if 'output_format' in prompt_data:
        output_format = prompt_data['output_format']
        print("✅ Output format loaded")
        print(f"   Format contains JSON: {'✅' if 'suggested_criteria' in output_format else '❌'}")

    # Test full prompt assembly
    full_prompt = []
    if 'system_context' in prompt_data:
        full_prompt.append(prompt_data['system_context'])
    full_prompt.append(rendered)
    if 'output_format' in prompt_data:
        full_prompt.append(prompt_data['output_format'])

    assembled_prompt = "\n\n".join(full_prompt)
    print("✅ Full prompt assembly works")
    print(f"   Final prompt length: {len(assembled_prompt)} characters")

    # Show preview
    print("\n📝 Prompt Preview (first 200 chars):")
    print("-" * 40)
    print(assembled_prompt[:200] + "...")
    print("-" * 40)

    print("\n🎉 Basic prompt management test passed!")
    return True

if __name__ == '__main__':
    test_basic_prompt_loading()