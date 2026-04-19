#!/usr/bin/env python3
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
