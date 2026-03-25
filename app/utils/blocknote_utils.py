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

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type', '')
            content_list = block.get('content', [])
            props = block.get('props', {})

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
                html_parts.append(f'<li>{text_html}</li>')
            elif block_type == 'numberedListItem':
                html_parts.append(f'<li>{text_html}</li>')
            else:
                # Default to paragraph
                if text_html:
                    html_parts.append(f'<p>{text_html}</p>')

        return ''.join(html_parts)

    except (json.JSONDecodeError, TypeError, ValueError):
        # Not JSON - convert newlines to <br> for plain text, or return as-is for HTML
        if '<' in content and '>' in content:
            return content  # Likely HTML already
        # Plain text: wrap paragraphs in <p> tags
        paragraphs = content.split('\n\n')
        return ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())


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
