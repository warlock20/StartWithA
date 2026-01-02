"""
Form Utilities
Helper functions for parsing and validating form data.
"""

from typing import List, Optional, Dict, Any
from werkzeug.datastructures import ImmutableMultiDict


def parse_form_list(
    form_data: str,
    delimiter: str = '\n',
    strip_empty: bool = True
) -> List[str]:
    """
    Parse delimited form data into list of strings.

    Args:
        form_data: String containing delimited data
        delimiter: Delimiter to split on (default: newline)
        strip_empty: If True, remove empty strings from result

    Returns:
        List of stripped strings

    Example:
        >>> parse_form_list("Item 1\\nItem 2\\n\\nItem 3")
        ['Item 1', 'Item 2', 'Item 3']
        >>> parse_form_list("a,b,c", delimiter=',')
        ['a', 'b', 'c']
    """
    if not form_data:
        return []

    items = [item.strip() for item in form_data.split(delimiter)]

    if strip_empty:
        items = [item for item in items if item]

    return items


def parse_multiline_form_field(
    form: ImmutableMultiDict,
    field_name: str,
    delimiter: str = '\n'
) -> List[str]:
    """
    Get multiline field from form and parse into list.

    Args:
        form: Flask request.form object
        field_name: Name of the form field
        delimiter: Delimiter to split on

    Returns:
        List of stripped, non-empty strings

    Example:
        >>> parse_multiline_form_field(request.form, 'contributing_factors')
        ['Factor 1', 'Factor 2', 'Factor 3']
    """
    field_value = form.get(field_name, '')
    return parse_form_list(field_value, delimiter)


def parse_multiple_form_lists(
    form: ImmutableMultiDict,
    field_names: List[str],
    delimiter: str = '\n'
) -> Dict[str, List[str]]:
    """
    Parse multiple multiline form fields at once.

    Args:
        form: Flask request.form object
        field_names: List of field names to parse
        delimiter: Delimiter to split on

    Returns:
        Dictionary mapping field names to parsed lists

    Example:
        >>> parse_multiple_form_lists(
        ...     request.form,
        ...     ['contributing_factors', 'prevention_steps', 'lessons_learned']
        ... )
        {
            'contributing_factors': ['Factor 1', 'Factor 2'],
            'prevention_steps': ['Step 1', 'Step 2'],
            'lessons_learned': ['Lesson 1']
        }
    """
    return {
        field_name: parse_multiline_form_field(form, field_name, delimiter)
        for field_name in field_names
    }


def get_form_list_or_default(
    form: ImmutableMultiDict,
    field_name: str,
    default: Optional[List[str]] = None,
    delimiter: str = '\n'
) -> List[str]:
    """
    Get form field as list or return default if empty.

    Args:
        form: Flask request.form object
        field_name: Name of the form field
        default: Default value to return if field is empty
        delimiter: Delimiter to split on

    Returns:
        List of strings or default value

    Example:
        >>> get_form_list_or_default(request.form, 'tags', default=['general'])
        ['general']  # if 'tags' field is empty
    """
    if default is None:
        default = []

    parsed = parse_multiline_form_field(form, field_name, delimiter)
    return parsed if parsed else default


def parse_checkbox_list(
    form: ImmutableMultiDict,
    prefix: str
) -> List[str]:
    """
    Parse checkbox inputs with a common prefix.

    Args:
        form: Flask request.form object
        prefix: Prefix of checkbox field names

    Returns:
        List of checkbox values that were checked

    Example:
        # HTML: <input type="checkbox" name="tag_finance" value="finance">
        #       <input type="checkbox" name="tag_tech" value="tech">
        >>> parse_checkbox_list(request.form, 'tag_')
        ['finance', 'tech']  # if both were checked
    """
    return [
        value for key, value in form.items()
        if key.startswith(prefix)
    ]


def parse_dynamic_numbered_fields(
    form: ImmutableMultiDict,
    field_prefix: str,
    max_fields: int = 50
) -> List[str]:
    """
    Parse dynamically numbered form fields (e.g., bull_case_1, bull_case_2, ...).

    Args:
        form: Flask request.form object
        field_prefix: Prefix of the field names (e.g., 'bull_case_')
        max_fields: Maximum number of fields to check

    Returns:
        List of non-empty field values in order

    Example:
        # HTML: <input name="bull_case_1" value="Strong moat">
        #       <input name="bull_case_2" value="Growing market">
        >>> parse_dynamic_numbered_fields(request.form, 'bull_case_')
        ['Strong moat', 'Growing market']
    """
    values = []
    for i in range(1, max_fields + 1):
        field_name = f'{field_prefix}{i}'
        value = form.get(field_name, '').strip()
        if value:
            values.append(value)

    return values


def get_form_value(
    form: ImmutableMultiDict,
    field_name: str,
    value_type: type = str,
    default: Any = None
) -> Any:
    """
    Get form value with type conversion and default handling.

    Args:
        form: Flask request.form object
        field_name: Name of the form field
        value_type: Type to convert value to (int, float, str, bool)
        default: Default value if field is missing or conversion fails

    Returns:
        Converted value or default

    Example:
        >>> get_form_value(request.form, 'age', int, default=0)
        25
        >>> get_form_value(request.form, 'price', float, default=0.0)
        99.99
    """
    try:
        value = form.get(field_name, type=value_type)
        return value if value is not None else default
    except (ValueError, TypeError):
        return default


def validate_required_fields(
    form: ImmutableMultiDict,
    required_fields: List[str]
) -> tuple[bool, Optional[str]]:
    """
    Validate that all required fields are present and non-empty.

    Args:
        form: Flask request.form object
        required_fields: List of required field names

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> is_valid, error = validate_required_fields(
        ...     request.form,
        ...     ['name', 'email', 'password']
        ... )
        >>> if not is_valid:
        ...     flash(error, 'error')
    """
    missing_fields = []

    for field_name in required_fields:
        value = form.get(field_name, '').strip()
        if not value:
            missing_fields.append(field_name.replace('_', ' ').title())

    if missing_fields:
        if len(missing_fields) == 1:
            return False, f"Please fill in the {missing_fields[0]} field"
        else:
            fields_str = ', '.join(missing_fields[:-1]) + f' and {missing_fields[-1]}'
            return False, f"Please fill in the following fields: {fields_str}"

    return True, None


def parse_tags_from_text(
    text: str,
    tag_prefix: str = '#'
) -> List[str]:
    """
    Extract hashtags from text.

    Args:
        text: Text containing hashtags
        tag_prefix: Character that prefixes tags (default: '#')

    Returns:
        List of tags (without the prefix character)

    Example:
        >>> parse_tags_from_text("Great analysis #tech #ai #investing")
        ['tech', 'ai', 'investing']
    """
    if not text:
        return []

    words = text.split()
    tags = [
        word[len(tag_prefix):].strip('.,!?;:')
        for word in words
        if word.startswith(tag_prefix) and len(word) > len(tag_prefix)
    ]

    return list(set(tags))  # Remove duplicates


def clean_form_text(
    text: str,
    max_length: Optional[int] = None
) -> str:
    """
    Clean and normalize form text input.

    Args:
        text: Input text to clean
        max_length: Maximum length to truncate to (None = no limit)

    Returns:
        Cleaned text

    Example:
        >>> clean_form_text("  Hello\\n\\nWorld  ")
        'Hello World'
        >>> clean_form_text("Long text here", max_length=10)
        'Long text...'
    """
    if not text:
        return ''

    # Normalize whitespace
    cleaned = ' '.join(text.split())

    # Truncate if needed
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length - 3] + '...'

    return cleaned
