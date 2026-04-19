#!/usr/bin/env python3
"""Test ArgosService has companion methods"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_argos_has_companion_context():
    """CompanionContext dataclass exists in argos module"""
    from app.services.argos.core import CompanionContext
    assert CompanionContext is not None
    print("PASS: CompanionContext importable from argos")


def test_argos_has_companion_methods():
    """ArgosService has all companion methods"""
    from app.services.argos.core import ArgosService
    required_methods = [
        'build_research_context',
        'generate_brief',
        'ask_companion',
        'generate_counter_evidence',
        'wrap_up_session',
    ]
    for method in required_methods:
        assert hasattr(ArgosService, method), f"Missing method: {method}"
    print("PASS: ArgosService has all companion methods")


def test_companion_context_serializes():
    """CompanionContext.to_dict() works correctly"""
    from app.services.argos.core import CompanionContext
    context = CompanionContext(
        company_name='Test Corp',
        company_id=1,
        sector_name='Technology',
        step_name='Competitive Analysis',
        step_description='Analyze competitive position',
        step_index=2,
        research_questions='- What is the competitive moat?',
        prior_findings='- Strong market position',
        red_flags='High debt ratio',
        green_flags='Strong cash flow',
        investment_thesis='Durable moat due to switching costs',
        journal_summary='No prior decisions',
        mistake_summary='No past mistakes',
        pattern_summary='- Confirmation bias (impact: 8/10)',
    )
    d = context.to_dict()
    assert d['company_name'] == 'Test Corp'
    assert d['pattern_summary'] == '- Confirmation bias (impact: 8/10)'
    assert 'journal_summary' in d
    assert 'mistake_summary' in d
    print("PASS: CompanionContext serializes correctly")


if __name__ == '__main__':
    test_argos_has_companion_context()
    test_argos_has_companion_methods()
    test_companion_context_serializes()
    print("\nAll Argos companion tests passed!")
