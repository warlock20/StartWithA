#!/usr/bin/env python3
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

"""Test Argos enrichment with journal entries and pattern recognition data"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.config import InsightCategory, CONTEXT_RULE_MATRIX, CONFIDENCE_RULES


def test_insight_categories_include_journal_and_pattern():
    """InsightCategory enum has JOURNAL_INSIGHT and PATTERN_WARNING"""
    assert hasattr(InsightCategory, 'JOURNAL_INSIGHT'), "Missing JOURNAL_INSIGHT category"
    assert hasattr(InsightCategory, 'PATTERN_WARNING'), "Missing PATTERN_WARNING category"
    assert InsightCategory.JOURNAL_INSIGHT.value == 'journal_insight'
    assert InsightCategory.PATTERN_WARNING.value == 'pattern_warning'
    print("PASS: InsightCategory has journal and pattern categories")


def test_context_rule_matrix_includes_new_categories():
    """CONTEXT_RULE_MATRIX includes JOURNAL_INSIGHT and PATTERN_WARNING for all step types"""
    for step_type in ['checklist', 'free_research', 'thesis', 'completion']:
        rules = CONTEXT_RULE_MATRIX[step_type]
        assert InsightCategory.JOURNAL_INSIGHT in rules, f"Missing JOURNAL_INSIGHT in {step_type}"
        assert InsightCategory.PATTERN_WARNING in rules, f"Missing PATTERN_WARNING in {step_type}"
    print("PASS: CONTEXT_RULE_MATRIX includes new categories")


def test_confidence_rules_include_new_categories():
    """CONFIDENCE_RULES includes JOURNAL_INSIGHT and PATTERN_WARNING"""
    assert InsightCategory.JOURNAL_INSIGHT in CONFIDENCE_RULES, "Missing JOURNAL_INSIGHT in CONFIDENCE_RULES"
    assert InsightCategory.PATTERN_WARNING in CONFIDENCE_RULES, "Missing PATTERN_WARNING in CONFIDENCE_RULES"
    print("PASS: CONFIDENCE_RULES includes new categories")


if __name__ == '__main__':
    test_insight_categories_include_journal_and_pattern()
    test_context_rule_matrix_includes_new_categories()
    test_confidence_rules_include_new_categories()
    print("\nAll Argos enrichment tests passed!")
