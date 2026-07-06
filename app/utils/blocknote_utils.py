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

"""
Utility functions for working with BlockNote content
"""
import json
import re


def blocknote_to_text(content):
    """
    Convert BlockNote JSON format to plain text for previews

    Args:
        content (str): BlockNote JSON content

    Returns:
        str: Plain text extracted from BlockNote blocks
    """
    if not content or not content.strip():
        return ''

    # Check if it's JSON (BlockNote format)
    try:
        blocks = json.loads(content)
        if not isinstance(blocks, list):
            return ''

        text_parts = []

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type', '')
            content_list = block.get('content', [])

            # Extract text from content array
            if isinstance(content_list, list):
                for item in content_list:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text = item.get('text', '')
                        if text:
                            text_parts.append(text)

        return ' '.join(text_parts)

    except (json.JSONDecodeError, TypeError, ValueError):
        # Not JSON - might be HTML from old Quill editor
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def blocknote_to_html(content):
    """
    Convert BlockNote JSON format to HTML

    Args:
        content (str): BlockNote JSON content

    Returns:
        str: HTML representation of BlockNote blocks
    """
    if not content or not content.strip():
        return ''

    try:
        blocks = json.loads(content)
        if not isinstance(blocks, list):
            return content  # Return as-is if not valid JSON

        html_parts = []
        prev_type = None

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type', '')
            content_list = block.get('content', [])
            props = block.get('props', {})

            # Close open list if switching away from list type
            if prev_type == 'bulletListItem' and block_type != 'bulletListItem':
                html_parts.append('</ul>')
            elif prev_type == 'numberedListItem' and block_type != 'numberedListItem':
                html_parts.append('</ol>')

            # Extract text with styling
            text_html = ''
            if isinstance(content_list, list):
                for item in content_list:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text = item.get('text', '')
                        styles = item.get('styles', {})

                        # Apply inline styles
                        if styles.get('bold'):
                            text = f'<strong>{text}</strong>'
                        if styles.get('italic'):
                            text = f'<em>{text}</em>'
                        if styles.get('underline'):
                            text = f'<u>{text}</u>'
                        if styles.get('strike'):
                            text = f'<s>{text}</s>'

                        text_html += text

            # Convert block types to HTML
            if block_type == 'heading':
                level = props.get('level', 1)
                html_parts.append(f'<h{level}>{text_html}</h{level}>')
            elif block_type == 'paragraph':
                html_parts.append(f'<p>{text_html}</p>')
            elif block_type == 'bulletListItem':
                if prev_type != 'bulletListItem':
                    html_parts.append('<ul>')
                html_parts.append(f'<li>{text_html}</li>')
            elif block_type == 'numberedListItem':
                if prev_type != 'numberedListItem':
                    html_parts.append('<ol>')
                html_parts.append(f'<li>{text_html}</li>')
            else:
                # Default to paragraph
                if text_html:
                    html_parts.append(f'<p>{text_html}</p>')

            prev_type = block_type

        # Close any trailing open list
        if prev_type == 'bulletListItem':
            html_parts.append('</ul>')
        elif prev_type == 'numberedListItem':
            html_parts.append('</ol>')

        return ''.join(html_parts)

    except (json.JSONDecodeError, TypeError, ValueError):
        # Not JSON - convert newlines to <br> for plain text, or return as-is for HTML
        if '<' in content and '>' in content:
            return content  # Likely HTML already
        # Plain text / markdown: render formatting
        return _markdown_to_html(content)


def _markdown_to_html(text):
    """Convert simple markdown-style text to HTML."""
    lines = text.split('\n')
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue

        # Bold: **text**
        stripped = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)

        # Headings
        if stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h5>{stripped[4:]}</h5>')
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h4>{stripped[3:]}</h4>')
        elif stripped.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h3>{stripped[2:]}</h3>')
        # List items (- item)
        elif stripped.startswith('- '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'<li>{stripped[2:]}</li>')
        # Horizontal rule
        elif stripped == '---':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('<hr>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{stripped}</p>')

    if in_list:
        html_parts.append('</ul>')

    return ''.join(html_parts)


def blocknote_preview(content, max_length=120):
    """
    Generate a preview text from BlockNote content

    Args:
        content (str): BlockNote JSON content
        max_length (int): Maximum length of preview text

    Returns:
        str: Preview text truncated to max_length
    """
    text = blocknote_to_text(content)

    if len(text) <= max_length:
        return text

    # Truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')

    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + '...'
