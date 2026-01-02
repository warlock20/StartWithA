#!/usr/bin/env python
"""
Import YAML prompts into PromptVersion database table.

This script reads all YAML prompt files and creates PromptVersion records
for version tracking and A/B testing.
"""

import os
import yaml
from datetime import datetime
from run import app
from app import db
from app.models import PromptVersion

def import_prompts():
    """Import all YAML prompts into the database."""

    prompts_dir = 'app/services/ai/prompts'
    imported_count = 0
    skipped_count = 0

    # Categories to scan
    categories = [
        'intelligence',
        'kill_checklist',
        'research_template',
        'research_journal',
        'sector_research',
        'competitor_analysis',
        'document_processing'
    ]

    with app.app_context():
        print("Starting prompt import...\n")

        for category in categories:
            category_dir = os.path.join(prompts_dir, category)

            if not os.path.exists(category_dir):
                print(f"⚠️  Category directory not found: {category}")
                continue

            # Find all YAML files in category
            yaml_files = [f for f in os.listdir(category_dir) if f.endswith('.yaml')]

            print(f"\n📁 Category: {category}")
            print(f"   Found {len(yaml_files)} YAML files")

            for yaml_file in yaml_files:
                file_path = os.path.join(category_dir, yaml_file)

                try:
                    # Read YAML file
                    with open(file_path, 'r') as f:
                        prompt_data = yaml.safe_load(f)

                    if not prompt_data:
                        print(f"   ⚠️  Skipping empty file: {yaml_file}")
                        skipped_count += 1
                        continue

                    # Extract fields
                    name = prompt_data.get('name')
                    if not name:
                        print(f"   ⚠️  Skipping {yaml_file}: no 'name' field")
                        skipped_count += 1
                        continue

                    # Check if already exists
                    existing = PromptVersion.query.filter_by(
                        name=name,
                        version=prompt_data.get('version', '1.0')
                    ).first()

                    if existing:
                        print(f"   ⏭️  Already exists: {name} v{prompt_data.get('version', '1.0')}")
                        skipped_count += 1
                        continue

                    # Create new PromptVersion
                    prompt_version = PromptVersion(
                        name=name,
                        category=prompt_data.get('category', category),
                        version=prompt_data.get('version', '1.0'),
                        description=prompt_data.get('description', ''),
                        template=prompt_data.get('template', ''),
                        system_context=prompt_data.get('system_context', ''),
                        preferred_provider=prompt_data.get('preferred_provider', 'claude'),
                        model=prompt_data.get('model'),
                        max_tokens=prompt_data.get('max_tokens'),
                        temperature=prompt_data.get('temperature'),
                        is_active=True,
                        is_default=True,
                        created_by='import_script',
                        notes=prompt_data.get('tuning_notes', ''),
                        created_at=datetime.utcnow(),
                        activated_at=datetime.utcnow()
                    )

                    db.session.add(prompt_version)
                    print(f"   ✅ Imported: {name} v{prompt_data.get('version', '1.0')}")
                    imported_count += 1

                except Exception as e:
                    print(f"   ❌ Error importing {yaml_file}: {e}")
                    skipped_count += 1
                    continue

        # Commit all changes
        try:
            db.session.commit()
            print(f"\n{'='*60}")
            print(f"✅ Import complete!")
            print(f"   Imported: {imported_count} prompts")
            print(f"   Skipped:  {skipped_count} prompts")
            print(f"{'='*60}\n")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Failed to commit: {e}")
            return False

    return True


if __name__ == '__main__':
    import_prompts()
