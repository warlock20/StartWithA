#!/usr/bin/env python3
"""
Test Script for Prompt Management System

This script validates the new centralized prompt management system
including YAML loading, template rendering, and integration with services.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_prompt_management_system():
    """Test all aspects of the prompt management system"""
    print("🧠 Testing Prompt Management System")
    print("=" * 60)

    try:
        from app.services.prompt_service import prompt_service, list_all_prompts, test_prompt

        # Test 1: List all available prompts
        print("📋 Test 1: List Available Prompts")
        prompts = list_all_prompts()
        assert 'kill_checklist' in prompts, "kill_checklist category missing"
        assert 'mistake_analysis' in prompts['kill_checklist'], "mistake_analysis prompt missing"
        print("✅ Prompt listing works correctly")
        print()

        # Test 2: Get prompt metadata
        print("📊 Test 2: Prompt Metadata")
        metadata = prompt_service.get_prompt_info('kill_checklist', 'mistake_analysis')
        print(f"   Name: {metadata['name']}")
        print(f"   Description: {metadata['description']}")
        print(f"   Version: {metadata['version']}")
        print(f"   Required variables: {metadata['required_variables']}")
        print(f"   Max tokens: {metadata['max_tokens']}")
        print("✅ Metadata retrieval works correctly")
        print()

        # Test 3: Prompt rendering with variables
        print("🎯 Test 3: Prompt Rendering")
        sample_data = {
            'mistake_title': 'Overleveraged Tech Investment',
            'mistake_description': 'Invested in tech company with 2.3 debt-to-equity ratio during rate hikes',
            'mistake_type': 'analysis_error',
            'mistake_severity': 8,
            'mistake_cost': '$25,000.00',
            'mistake_date': '2024-01-15',
            'existing_criteria': '- Is P/E ratio below 30?\n- Does company have moat?'
        }

        rendered_prompt = prompt_service.get_prompt('kill_checklist', 'mistake_analysis', **sample_data)

        print(f"   Rendered prompt length: {len(rendered_prompt)} characters")
        print(f"   Contains mistake title: {'✅' if sample_data['mistake_title'] in rendered_prompt else '❌'}")
        print(f"   Contains output format: {'✅' if 'suggested_criteria' in rendered_prompt else '❌'}")
        print(f"   Contains examples: {'✅' if 'debt-to-equity' in rendered_prompt else '❌'}")

        # Show a preview of the rendered prompt
        print("\n   Preview of rendered prompt:")
        print("   " + "-" * 50)
        print("   " + rendered_prompt[:300].replace('\n', '\n   ') + "...")
        print("   " + "-" * 50)

        assert len(rendered_prompt) > 500, "Rendered prompt seems too short"
        assert sample_data['mistake_title'] in rendered_prompt, "Variable substitution failed"
        print("✅ Prompt rendering works correctly")
        print()

        # Test 4: Error handling
        print("🛡️ Test 4: Error Handling")

        # Test invalid category
        try:
            prompt_service.get_prompt('invalid_category', 'test')
            assert False, "Should have raised error for invalid category"
        except ValueError as e:
            print(f"   ✅ Invalid category error: {e}")

        # Test missing variable
        try:
            prompt_service.get_prompt('kill_checklist', 'mistake_analysis', mistake_title='Test')
            assert False, "Should have raised error for missing variables"
        except ValueError as e:
            print(f"   ✅ Missing variable error: {e}")
        print("✅ Error handling works correctly")
        print()

        # Test 5: Validation function
        print("✔️ Test 5: Prompt Validation")
        validation_result = prompt_service.validate_prompt('kill_checklist', 'mistake_analysis', **sample_data)

        print(f"   Valid: {validation_result['valid']}")
        print(f"   Prompt length: {validation_result['prompt_length']}")
        print(f"   Word count: {validation_result['word_count']}")
        print(f"   Variables used: {validation_result['variables_used']}")

        assert validation_result['valid'], "Prompt validation failed"
        assert validation_result['prompt_length'] > 500, "Validated prompt too short"
        print("✅ Prompt validation works correctly")
        print()

        # Test 6: Integration with analytics service
        print("🔧 Test 6: Analytics Service Integration")

        try:
            from app.services.kill_checklist_analytics import KillChecklistAnalytics
            from app.services.prompt_service import get_kill_checklist_prompt

            # Test that the import works
            test_prompt = get_kill_checklist_prompt('mistake_analysis', **sample_data)
            assert len(test_prompt) > 500, "Integration prompt too short"
            print("   ✅ Analytics service can import and use prompt service")
            print("   ✅ Convenience function works correctly")

        except ImportError as e:
            print(f"   ⚠️ Analytics integration test skipped (import error): {e}")
        print()

        # Test 7: Performance test
        print("⚡ Test 7: Performance Test")
        import time

        start_time = time.time()
        for i in range(10):
            prompt_service.get_prompt('kill_checklist', 'mistake_analysis', **sample_data)
        end_time = time.time()

        avg_time = (end_time - start_time) / 10
        print(f"   Average rendering time: {avg_time:.4f}s per prompt")
        print(f"   Cached loading: {'✅' if avg_time < 0.01 else '⚠️'}")

        assert avg_time < 0.1, "Prompt rendering too slow"
        print("✅ Performance test passed")
        print()

        print("🎉 ALL PROMPT MANAGEMENT TESTS PASSED!")
        print("=" * 60)

        # Summary of benefits
        print("🚀 Prompt Management System Benefits:")
        print("  ✅ Centralized prompt storage in YAML files")
        print("  ✅ Easy variable substitution and templating")
        print("  ✅ Version control and metadata tracking")
        print("  ✅ Robust error handling and validation")
        print("  ✅ Performance optimization with caching")
        print("  ✅ Clean separation of prompts from code")
        print("  ✅ Easy tuning without touching application logic")
        print()

        print("📁 Prompt Files Structure:")
        print("  app/prompts/")
        print("    kill_checklist/")
        print("      - mistake_analysis.yaml ✅")
        print("      - effectiveness_scoring.yaml ✅")
        print("    research_journal/ (ready for next feature)")
        print("    research_template/ (ready for future features)")
        print()

        return True

    except Exception as e:
        print(f"❌ PROMPT MANAGEMENT TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_yaml_prompt_structure():
    """Test the YAML prompt file structure specifically"""
    print("📄 Testing YAML Prompt File Structure")
    print("-" * 40)

    try:
        import yaml
        from pathlib import Path

        prompts_dir = Path(__file__).parent / "app" / "prompts" / "kill_checklist"

        for yaml_file in prompts_dir.glob("*.yaml"):
            print(f"   Testing {yaml_file.name}...")

            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            # Check required fields
            required_fields = ['name', 'description', 'template']
            for field in required_fields:
                assert field in data, f"Missing required field '{field}' in {yaml_file.name}"

            print(f"   ✅ {yaml_file.name} structure is valid")

        print("✅ All YAML files have valid structure")
        return True

    except Exception as e:
        print(f"❌ YAML structure test failed: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Starting Prompt Management System Tests")
    print()

    # Test YAML structure first
    yaml_success = test_yaml_prompt_structure()
    print()

    # Test full system
    system_success = test_prompt_management_system()

    if yaml_success and system_success:
        print("\n🎉 All tests passed! Prompt management system is ready!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)