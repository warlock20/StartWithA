"""
Authorization Utilities
Centralized authorization and access control helpers.
"""

from typing import Optional, Tuple, Any
from functools import wraps
from flask import jsonify, abort
from flask_login import current_user
import os

# Create a list of allowed emails in your Railway Variables
ALLOWED_USERS = os.environ.get('ALLOWED_USERS', '').split(',')

def is_authorized(email):
    # If ALLOWED_USERS is empty, everyone is allowed (dev mode)
    if not ALLOWED_USERS or ALLOWED_USERS == ['']:
        return True
    return email in ALLOWED_USERS

def check_resource_ownership(
    resource_obj: Any,
    user_id: int,
    user_id_attr: str = 'user_id'
) -> bool:
    """
    Check if a resource belongs to a specific user.

    Args:
        resource_obj: The resource object to check
        user_id: The user ID to verify against
        user_id_attr: Attribute name containing the user_id (default: 'user_id')

    Returns:
        True if user owns the resource, False otherwise

    Example:
        >>> company = Company.query.get(123)
        >>> if not check_resource_ownership(company, current_user.id):
        ...     abort(403)
    """
    if resource_obj is None:
        return False

    resource_user_id = getattr(resource_obj, user_id_attr, None)
    return resource_user_id == user_id


def require_resource_ownership(
    resource_obj: Any,
    user_id: int,
    user_id_attr: str = 'user_id',
    error_message: str = 'Access denied',
    abort_code: int = 403
) -> None:
    """
    Require resource ownership or abort with 403.

    Args:
        resource_obj: The resource object to check
        user_id: The user ID to verify against
        user_id_attr: Attribute name containing the user_id (default: 'user_id')
        error_message: Custom error message
        abort_code: HTTP status code to use (default: 403)

    Raises:
        403 Forbidden if ownership check fails

    Example:
        >>> company = Company.query.get_or_404(company_id)
        >>> require_resource_ownership(company, current_user.id)
        >>> # Continue with authorized operations...
    """
    if not check_resource_ownership(resource_obj, user_id, user_id_attr):
        abort(abort_code, description=error_message)


def check_ownership_json(
    resource_obj: Any,
    user_id: int,
    user_id_attr: str = 'user_id',
    error_message: str = 'Access denied'
) -> Optional[Tuple[dict, int]]:
    """
    Check resource ownership and return JSON error if unauthorized.
    Used for AJAX/API endpoints.

    Args:
        resource_obj: The resource object to check
        user_id: The user ID to verify against
        user_id_attr: Attribute name containing the user_id
        error_message: Custom error message

    Returns:
        Tuple of (error_dict, 403) if unauthorized, None if authorized

    Example:
        >>> mistake = MistakeLog.query.get_or_404(mistake_id)
        >>> error = check_ownership_json(mistake, current_user.id)
        >>> if error:
        ...     return error
        >>> # Continue with authorized operations...
    """
    if not check_resource_ownership(resource_obj, user_id, user_id_attr):
        return jsonify({'error': error_message}), 403
    return None


def require_ownership(user_id_attr: str = 'user_id'):
    """
    Decorator to require resource ownership for a route.
    The route function must have a parameter that retrieves the resource.

    Args:
        user_id_attr: Attribute name containing the user_id (default: 'user_id')

    Example:
        @app.route('/mistake/<int:mistake_id>/edit')
        @login_required
        @require_ownership()
        def edit_mistake(mistake_id):
            mistake = MistakeLog.query.get_or_404(mistake_id)
            # Ownership already verified by decorator
            return render_template('edit.html', mistake=mistake)

    Note:
        This decorator expects the resource to be fetched inside the wrapped function.
        For more complex scenarios, use check_resource_ownership() directly.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Call the original function
            result = f(*args, **kwargs)
            return result
        return decorated_function
    return decorator


def verify_user_owns_resources(
    *resources: Any,
    user_id: int,
    user_id_attr: str = 'user_id'
) -> bool:
    """
    Verify user owns ALL provided resources.

    Args:
        *resources: Variable number of resource objects to check
        user_id: The user ID to verify against
        user_id_attr: Attribute name containing the user_id

    Returns:
        True if user owns all resources, False otherwise

    Example:
        >>> company = Company.query.get(1)
        >>> project = ResearchProject.query.get(2)
        >>> if verify_user_owns_resources(company, project, user_id=current_user.id):
        ...     # User owns both resources
        ...     pass
    """
    return all(
        check_resource_ownership(resource, user_id, user_id_attr)
        for resource in resources
        if resource is not None
    )


def get_user_resource_or_403(
    model_class,
    resource_id: int,
    user_id: int,
    user_id_attr: str = 'user_id',
    error_message: str = 'Resource not found or access denied'
):
    """
    Get resource by ID and verify ownership in one operation.

    Args:
        model_class: SQLAlchemy model class
        resource_id: ID of the resource to fetch
        user_id: User ID to verify ownership
        user_id_attr: Attribute name containing the user_id
        error_message: Custom error message

    Returns:
        The resource object if found and owned by user

    Raises:
        404 if not found, 403 if unauthorized

    Example:
        >>> # Instead of:
        >>> # company = Company.query.get_or_404(company_id)
        >>> # require_resource_ownership(company, current_user.id)
        >>>
        >>> # Use:
        >>> company = get_user_resource_or_403(Company, company_id, current_user.id)
    """
    resource = model_class.query.get_or_404(resource_id)
    require_resource_ownership(resource, user_id, user_id_attr, error_message)
    return resource


def filter_by_user_ownership(
    query,
    user_id: int,
    user_id_attr: str = 'user_id'
):
    """
    Add user ownership filter to a query.

    Args:
        query: SQLAlchemy query object
        user_id: User ID to filter by
        user_id_attr: Attribute name containing the user_id

    Returns:
        Query with user ownership filter applied

    Example:
        >>> query = Company.query
        >>> user_companies = filter_by_user_ownership(query, current_user.id).all()
    """
    return query.filter_by(**{user_id_attr: user_id})
