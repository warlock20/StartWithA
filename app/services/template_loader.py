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
Template Loader Service
Handles loading, validating, and processing checklist templates from YAML files
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from flask import current_app


class TemplateValidationError(Exception):
    """Raised when a template fails validation"""
    pass


class ChecklistTemplateLoader:
    """Service for loading and managing checklist templates"""

    REQUIRED_FIELDS = ['name', 'description', 'items']
    OPTIONAL_FIELDS = ['category', 'difficulty', 'estimated_time', 'icon']
    VALID_CATEGORIES = ['general', 'financial', 'investing_style', 'risk', 'custom']
    VALID_DIFFICULTIES = ['beginner', 'intermediate', 'advanced']

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the template loader

        Args:
            templates_dir: Path to templates directory. If None, uses default app/checklists/checklist_templates
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to app/checklists/checklist_templates
            app_root = Path(__file__).parent.parent
            self.templates_dir = app_root / 'checklists/checklist_templates'

    def load_template(self, template_name: str) -> Dict:
        """
        Load a template from a YAML file

        Args:
            template_name: Name of the template (without .yaml extension) or full path

        Returns:
            Dict containing the parsed template data

        Raises:
            FileNotFoundError: If template file doesn't exist
            TemplateValidationError: If template is invalid
        """
        # Handle both template name and full path
        if template_name.endswith('.yaml') or template_name.endswith('.yml'):
            template_path = Path(template_name)
        else:
            template_path = self.templates_dir / f"{template_name}.yaml"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TemplateValidationError(f"Invalid YAML in template {template_name}: {e}")

        # Validate the template
        self._validate_template(template_data, template_name)

        return template_data

    def _validate_template(self, template_data: Dict, template_name: str):
        """
        Validate template structure and content

        Args:
            template_data: Parsed template dictionary
            template_name: Name of the template for error messages

        Raises:
            TemplateValidationError: If validation fails
        """
        if not isinstance(template_data, dict):
            raise TemplateValidationError(f"Template {template_name} must be a dictionary")

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in template_data:
                raise TemplateValidationError(
                    f"Template {template_name} missing required field: {field}"
                )

        # Validate category
        if 'category' in template_data:
            if template_data['category'] not in self.VALID_CATEGORIES:
                raise TemplateValidationError(
                    f"Invalid category '{template_data['category']}' in {template_name}. "
                    f"Must be one of: {', '.join(self.VALID_CATEGORIES)}"
                )

        # Validate difficulty
        if 'difficulty' in template_data:
            if template_data['difficulty'] not in self.VALID_DIFFICULTIES:
                raise TemplateValidationError(
                    f"Invalid difficulty '{template_data['difficulty']}' in {template_name}. "
                    f"Must be one of: {', '.join(self.VALID_DIFFICULTIES)}"
                )

        # Validate items structure
        items = template_data.get('items', [])
        if not isinstance(items, list) or len(items) == 0:
            raise TemplateValidationError(
                f"Template {template_name} must have at least one item"
            )

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise TemplateValidationError(
                    f"Item {i} in template {template_name} must be a dictionary"
                )
            if 'text' not in item:
                raise TemplateValidationError(
                    f"Item {i} in template {template_name} missing 'text' field"
                )

            # Validate subitems if present
            if 'subitems' in item:
                subitems = item['subitems']
                if not isinstance(subitems, list):
                    raise TemplateValidationError(
                        f"Subitems in item {i} of {template_name} must be a list"
                    )
                for j, subitem in enumerate(subitems):
                    if not isinstance(subitem, dict):
                        raise TemplateValidationError(
                            f"Subitem {j} in item {i} of {template_name} must be a dictionary"
                        )
                    if 'text' not in subitem:
                        raise TemplateValidationError(
                            f"Subitem {j} in item {i} of {template_name} missing 'text' field"
                        )

    def list_available_templates(self) -> List[Dict]:
        """
        List all available templates in the templates directory

        Returns:
            List of dicts with template metadata (name, description, category, etc.)
        """
        templates = []

        if not self.templates_dir.exists():
            return templates

        for yaml_file in self.templates_dir.glob('*.yaml'):
            try:
                template_data = self.load_template(yaml_file.stem)
                templates.append({
                    'id': yaml_file.stem,
                    'name': template_data.get('name', yaml_file.stem),
                    'description': template_data.get('description', ''),
                    'category': template_data.get('category', 'custom'),
                    'difficulty': template_data.get('difficulty', 'intermediate'),
                    'estimated_time': template_data.get('estimated_time', ''),
                    'icon': template_data.get('icon', '📋'),
                    'item_count': len(template_data.get('items', []))
                })
            except (FileNotFoundError, TemplateValidationError) as e:
                current_app.logger.warning(f"Failed to load template {yaml_file.stem}: {e}")
                continue

        return templates

    def create_checklist_from_template(self, template_name: str, checklist, db) -> Tuple[int, int]:
        """
        Populate a checklist with items from a template

        Args:
            template_name: Name of the template to load
            checklist: Checklist model instance to populate
            db: Database session

        Returns:
            Tuple of (items_created, subitems_created) counts
        """
        from app.models import ChecklistItem

        template_data = self.load_template(template_name)
        items = template_data.get('items', [])

        items_created = 0
        subitems_created = 0

        for order, item_data in enumerate(items):
            # Create main item
            main_item = ChecklistItem(
                text=item_data['text'],
                llm_prompt=item_data.get('llm_prompt'),
                checklist=checklist,
                parent_id=None,
                order=order
            )
            db.session.add(main_item)
            db.session.flush()  # Get the main_item.id
            items_created += 1

            # Create subitems if present
            subitems = item_data.get('subitems', [])
            for sub_order, subitem_data in enumerate(subitems):
                subitem = ChecklistItem(
                    text=subitem_data['text'],
                    llm_prompt=subitem_data.get('llm_prompt'),
                    checklist=checklist,
                    parent_id=main_item.id,
                    order=sub_order
                )
                db.session.add(subitem)
                subitems_created += 1

        return items_created, subitems_created

    def export_checklist_to_yaml(self, checklist, output_path: Optional[str] = None) -> str:
        """
        Export a checklist to YAML format

        Args:
            checklist: Checklist model instance to export
            output_path: Optional path to save the YAML file

        Returns:
            YAML string representation of the checklist
        """
        # Build template structure
        template_dict = {
            'name': checklist.name,
            'description': checklist.description or 'Custom checklist',
            'category': 'custom',
            'difficulty': 'intermediate',
            'estimated_time': '',
            'icon': '📋',
            'items': []
        }

        # Get all top-level items (no parent)
        top_level_items = checklist.items.filter_by(parent_id=None).order_by('order').all()

        for item in top_level_items:
            item_dict = {
                'text': item.text,
            }

            if item.llm_prompt:
                item_dict['llm_prompt'] = item.llm_prompt

            # Get subitems
            subitems = checklist.items.filter_by(parent_id=item.id).order_by('order').all()
            if subitems:
                item_dict['subitems'] = []
                for subitem in subitems:
                    subitem_dict = {'text': subitem.text}
                    if subitem.llm_prompt:
                        subitem_dict['llm_prompt'] = subitem.llm_prompt
                    item_dict['subitems'].append(subitem_dict)

            template_dict['items'].append(item_dict)

        # Convert to YAML
        yaml_content = yaml.dump(
            template_dict,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

        # Add header comment
        header = f"# {checklist.name}\n# Exported from Investment Checklist App\n\n"
        yaml_content = header + yaml_content

        # Save to file if path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)

        return yaml_content


# Global instance
_template_loader = None


def get_template_loader() -> ChecklistTemplateLoader:
    """Get or create the global template loader instance"""
    global _template_loader
    if _template_loader is None:
        _template_loader = ChecklistTemplateLoader()
    return _template_loader
