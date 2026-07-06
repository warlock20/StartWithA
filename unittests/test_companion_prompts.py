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

"""Test companion prompt templates load correctly"""

import yaml
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PROMPTS_DIR = Path(__file__).parent.parent / "app" / "services" / "ai" / "prompts" / "companion"

REQUIRED_PROMPTS = [
    'research_brief',
    'live_companion',
    'counter_evidence',
    'session_wrapup',
]

REQUIRED_FIELDS = ['name', 'description', 'version', 'category', 'system_context', 'template']


def test_all_companion_prompts_exist():
    """All companion prompt YAML files exist"""
    assert PROMPTS_DIR.exists(), f"Companion prompts directory missing: {PROMPTS_DIR}"
    for name in REQUIRED_PROMPTS:
        path = PROMPTS_DIR / f"{name}.yaml"
        assert path.exists(), f"Missing prompt: {path}"
    print("PASS: All companion prompt files exist")


def test_all_companion_prompts_valid():
    """All companion prompts have required fields and valid templates"""
    for name in REQUIRED_PROMPTS:
        path = PROMPTS_DIR / f"{name}.yaml"
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        for field in REQUIRED_FIELDS:
            assert field in data, f"{name}.yaml missing required field: {field}"

        assert data['category'] == 'companion', f"{name}.yaml category should be 'companion'"
    print("PASS: All companion prompts have valid structure")


def test_live_companion_has_opinion_warning():
    """Live companion prompt includes opinion-warning rules"""
    path = PROMPTS_DIR / "live_companion.yaml"
    with open(path, 'r') as f:
        content = f.read()
    assert 'opinion' in content.lower(), "live_companion.yaml must include opinion-warning rules"
    print("PASS: Live companion includes opinion-warning rules")


if __name__ == '__main__':
    test_all_companion_prompts_exist()
    test_all_companion_prompts_valid()
    test_live_companion_has_opinion_warning()
    print("\nAll companion prompt tests passed!")
