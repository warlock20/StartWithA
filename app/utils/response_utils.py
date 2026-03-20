"""
Response Utilities
Standardized response formatting for API endpoints and AJAX requests.
"""

from typing import Optional, Dict, Any, Tuple
from flask import jsonify, Response
from datetime import datetime, date
from decimal import Decimal
from app.utils.time_utils import now_utc


def json_success(
    message: str = "Success",
    data: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
    **kwargs
) -> Tuple[Response, int]:
    """
    Create standardized success JSON response.

    Args:
        message: Success message
        data: Optional data dictionary
        status_code: HTTP status code (default: 200)
        **kwargs: Additional fields to include in response

    Returns:
        Tuple of (JSON response, status code)

    Example:
        >>> return json_success("User created", data={'user_id': 123})
        {'success': True, 'message': 'User created', 'data': {'user_id': 123}}
    """
    response = {
        'success': True,
        'message': message
    }

    if data:
        response['data'] = data

    # Add any additional fields
    response.update(kwargs)

    return jsonify(response), status_code


def json_error(
    message: str = "An error occurred",
    error: Optional[str] = None,
    status_code: int = 400,
    **kwargs
) -> Tuple[Response, int]:
    """
    Create standardized error JSON response.

    Args:
        message: Error message for user
        error: Technical error details (optional)
        status_code: HTTP status code (default: 400)
        **kwargs: Additional fields to include in response

    Returns:
        Tuple of (JSON response, status code)

    Example:
        >>> return json_error("Invalid email", error="Email format validation failed", status_code=400)
        {'success': False, 'message': 'Invalid email', 'error': 'Email format validation failed'}
    """
    response = {
        'success': False,
        'message': message,
        'error': error or message
    }

    # Add any additional fields
    response.update(kwargs)

    return jsonify(response), status_code


def json_not_found(
    resource: str = "Resource",
    resource_id: Optional[Any] = None
) -> Tuple[Response, int]:
    """
    Create standardized 404 not found response.

    Args:
        resource: Name of the resource that wasn't found
        resource_id: ID of the resource (optional)

    Returns:
        Tuple of (JSON response, 404)

    Example:
        >>> return json_not_found("Company", resource_id=123)
        {'success': False, 'message': 'Company with ID 123 not found'}
    """
    if resource_id:
        message = f"{resource} with ID {resource_id} not found"
    else:
        message = f"{resource} not found"

    return json_error(message, status_code=404)


def json_unauthorized(
    message: str = "Access denied"
) -> Tuple[Response, int]:
    """
    Create standardized 403 unauthorized response.

    Args:
        message: Unauthorized message

    Returns:
        Tuple of (JSON response, 403)

    Example:
        >>> return json_unauthorized("You don't have permission to edit this company")
    """
    return json_error(message, status_code=403)


def json_validation_error(
    message: str = "Validation failed",
    errors: Optional[Dict[str, list]] = None
) -> Tuple[Response, int]:
    """
    Create standardized validation error response.

    Args:
        message: Main validation error message
        errors: Dictionary of field-specific errors

    Returns:
        Tuple of (JSON response, 400)

    Example:
        >>> return json_validation_error(
        ...     "Form validation failed",
        ...     errors={
        ...         'email': ['Email is required', 'Email format is invalid'],
        ...         'password': ['Password must be at least 8 characters']
        ...     }
        ... )
    """
    response = {
        'success': False,
        'message': message
    }

    if errors:
        response['errors'] = errors

    return jsonify(response), 400


def json_response(
    success: bool = True,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    status_code: Optional[int] = None,
    **kwargs
) -> Tuple[Response, int]:
    """
    Generic JSON response builder with flexible options.

    Args:
        success: Whether operation was successful
        message: Response message
        data: Data to include in response
        error: Error details (if success=False)
        status_code: HTTP status code (defaults based on success)
        **kwargs: Additional fields

    Returns:
        Tuple of (JSON response, status code)

    Example:
        >>> return json_response(
        ...     success=True,
        ...     message="Transaction saved",
        ...     data={'transaction_id': 456},
        ...     timestamp=datetime.now().isoformat()
        ... )
    """
    if status_code is None:
        status_code = 200 if success else 400

    if success:
        return json_success(
            message=message or "Success",
            data=data,
            status_code=status_code,
            **kwargs
        )
    else:
        return json_error(
            message=message or "Error",
            error=error,
            status_code=status_code,
            **kwargs
        )


def json_with_timestamp(
    success: bool = True,
    message: str = "Success",
    data: Optional[Dict[str, Any]] = None,
    timestamp_format: str = 'iso'
) -> Tuple[Response, int]:
    """
    Create JSON response with timestamp.

    Args:
        success: Whether operation was successful
        message: Response message
        data: Data to include
        timestamp_format: 'iso' for ISO format, 'unix' for Unix timestamp

    Returns:
        Tuple of (JSON response, status code)

    Example:
        >>> return json_with_timestamp(True, "Saved", data={'id': 123})
        {
            'success': True,
            'message': 'Saved',
            'data': {'id': 123},
            'timestamp': '2024-01-15T10:30:00'
        }
    """
    now = now_utc()

    if timestamp_format == 'unix':
        timestamp = int(now.timestamp())
    else:
        timestamp = now.isoformat()

    return json_response(
        success=success,
        message=message,
        data=data,
        timestamp=timestamp
    )


def json_paginated(
    items: list,
    page: int,
    per_page: int,
    total: int,
    message: str = "Success"
) -> Tuple[Response, int]:
    """
    Create paginated JSON response.

    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total: Total number of items
        message: Response message

    Returns:
        Tuple of (JSON response, 200)

    Example:
        >>> return json_paginated(
        ...     items=companies,
        ...     page=2,
        ...     per_page=25,
        ...     total=150
        ... )
        {
            'success': True,
            'message': 'Success',
            'data': {'items': [...]},
            'pagination': {
                'page': 2,
                'per_page': 25,
                'total': 150,
                'pages': 6
            }
        }
    """
    pages = (total + per_page - 1) // per_page  # Ceiling division

    return json_success(
        message=message,
        data={'items': items},
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_prev': page > 1,
            'has_next': page < pages
        }
    )


def serialize_model_to_dict(
    obj: Any,
    fields: Optional[list] = None,
    exclude: Optional[list] = None
) -> Dict[str, Any]:
    """
    Serialize SQLAlchemy model to dictionary for JSON response.

    Args:
        obj: SQLAlchemy model instance
        fields: List of fields to include (None = all fields)
        exclude: List of fields to exclude

    Returns:
        Dictionary representation of the object

    Example:
        >>> company = Company.query.get(1)
        >>> company_dict = serialize_model_to_dict(
        ...     company,
        ...     fields=['id', 'name', 'ticker_symbol']
        ... )
        >>> return json_success(data=company_dict)
    """
    if exclude is None:
        exclude = []

    result = {}

    # Get all columns
    if fields is None:
        fields = [c.name for c in obj.__table__.columns]

    for field in fields:
        if field in exclude:
            continue

        value = getattr(obj, field, None)

        # Handle special types
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)

        result[field] = value

    return result


def json_created(
    message: str = "Created successfully",
    data: Optional[Dict[str, Any]] = None,
    resource_id: Optional[Any] = None,
    **kwargs
) -> Tuple[Response, int]:
    """
    Create standardized 201 Created response.

    Args:
        message: Success message
        data: Data to include
        resource_id: ID of created resource
        **kwargs: Additional fields

    Returns:
        Tuple of (JSON response, 201)

    Example:
        >>> return json_created(
        ...     message="Company created",
        ...     data={'company': company_dict},
        ...     resource_id=123
        ... )
    """
    response_data = data or {}

    if resource_id:
        response_data['id'] = resource_id

    return json_success(
        message=message,
        data=response_data,
        status_code=201,
        **kwargs
    )


def json_deleted(
    message: str = "Deleted successfully",
    resource_id: Optional[Any] = None
) -> Tuple[Response, int]:
    """
    Create standardized deletion success response.

    Args:
        message: Success message
        resource_id: ID of deleted resource

    Returns:
        Tuple of (JSON response, 200)

    Example:
        >>> return json_deleted("Company deleted", resource_id=123)
    """
    kwargs = {}
    if resource_id:
        kwargs['deleted_id'] = resource_id

    return json_success(message=message, **kwargs)


def json_updated(
    message: str = "Updated successfully",
    data: Optional[Dict[str, Any]] = None,
    resource_id: Optional[Any] = None
) -> Tuple[Response, int]:
    """
    Create standardized update success response.

    Args:
        message: Success message
        data: Updated data
        resource_id: ID of updated resource

    Returns:
        Tuple of (JSON response, 200)

    Example:
        >>> return json_updated(
        ...     message="Company updated",
        ...     data={'company': company_dict},
        ...     resource_id=123
        ... )
    """
    response_data = data or {}

    if resource_id:
        response_data['id'] = resource_id

    return json_success(message=message, data=response_data)
