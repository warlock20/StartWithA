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

        def _collect(items):
            """Pull text out of a content array.

            Inline content isn't only `text` items — a `link` carries its label in
            its own nested content array. Skipping those silently drops whole
            paragraphs whose only content is a link, which then read as empty.
            """
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get('type') == 'text':
                    text = item.get('text', '')
                    if text:
                        text_parts.append(text)
                elif isinstance(item.get('content'), list):
                    _collect(item['content'])          # link and other wrappers
                elif isinstance(item.get('content'), str) and item.get('content'):
                    text_parts.append(item['content'])

        def _walk(block_list):
            for block in block_list:
                if not isinstance(block, dict):
                    continue
                _collect(block.get('content', []))
                # Nested blocks (list items, toggles) hold their own content.
                children = block.get('children')
                if isinstance(children, list):
                    _walk(children)

        _walk(blocks)
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


def _as_blocks(content):
    """
    Coerce a stored value into a list of BlockNote blocks.

    Content that isn't a JSON array — NULL, empty, plain text from an older
    write, or malformed JSON — becomes a single paragraph so nothing is
    discarded.
    """
    if not content or not str(content).strip():
        return []

    def _para(value):
        return {'type': 'paragraph', 'props': {},
                'content': [{'type': 'text', 'text': value, 'styles': {}}]}

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else [_para(content)]
    except (json.JSONDecodeError, TypeError, ValueError):
        return [_para(content)]


def append_note(content, note, heading):
    """
    Append a dated note to a BlockNote document, returning the new document.

    The note keeps whatever formatting the editor produced — lists, bold,
    links — because its blocks are appended as-is rather than flattened to
    text. Plain strings are still accepted and become one paragraph.

    Args:
        content (str|None): existing BlockNote document
        note (str): the note to append, as BlockNote JSON or plain text
        heading (str): dated heading, e.g. '4 Aug 2026 — Deep Dive'

    Returns:
        str: JSON text of the combined document
    """
    heading_block = {'type': 'heading', 'props': {'level': 2},
                     'content': [{'type': 'text', 'text': heading, 'styles': {}}]}

    return json.dumps(_as_blocks(content) + [heading_block] + _as_blocks(note))
