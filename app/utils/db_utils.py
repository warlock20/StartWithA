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
Database Utilities
Helper functions for safe database operations and transaction handling.
"""

import logging
from contextlib import contextmanager
from typing import Optional, Tuple, Callable, Any
from flask import flash

logger = logging.getLogger(__name__)


@contextmanager
def safe_db_transaction(db_session, rollback_on_error: bool = True):
    """
    Context manager for safe database transactions with automatic rollback.

    Args:
        db_session: SQLAlchemy database session
        rollback_on_error: If True, rollback on exception (default: True)

    Yields:
        Database session

    Example:
        >>> with safe_db_transaction(db.session) as session:
        ...     user = User(name="John")
        ...     session.add(user)
        ...     # Automatically commits on success, rolls back on error
    """
    try:
        yield db_session
        db_session.commit()
    except Exception as e:
        if rollback_on_error:
            db_session.rollback()
        logger.exception(f"Database transaction failed: {e}")
        raise


def safe_commit(
    db_session,
    operation_name: str = "Operation",
    flash_success: bool = False,
    flash_error: bool = False,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Safely commit database changes with error handling and optional flash messages.

    Args:
        db_session: SQLAlchemy database session
        operation_name: Name of the operation for logging
        flash_success: If True, flash success message
        flash_error: If True, flash error message
        success_message: Custom success message (defaults to "{operation_name} successful")
        error_message: Custom error message prefix

    Returns:
        Tuple of (success: bool, error_message: Optional[str])

    Example:
        >>> user = User(name="John")
        >>> db.session.add(user)
        >>> success, error = safe_commit(
        ...     db.session,
        ...     operation_name="User creation",
        ...     flash_success=True
        ... )
        >>> if not success:
        ...     return redirect(url_for('error_page'))
    """
    try:
        db_session.commit()

        if flash_success:
            msg = success_message or f"{operation_name} successful"
            flash(msg, 'success')

        logger.info(f"{operation_name} completed successfully")
        return True, None

    except Exception as e:
        db_session.rollback()

        error_msg = f"{error_message or 'Error during ' + operation_name}: {str(e)}"
        logger.exception(error_msg)

        if flash_error:
            flash(error_msg, 'error')

        return False, error_msg


def safe_add_and_commit(
    db_session,
    obj: Any,
    operation_name: str = "Save",
    flash_success: bool = False,
    flash_error: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Add object to session and commit with error handling.

    Args:
        db_session: SQLAlchemy database session
        obj: Object to add
        operation_name: Name of the operation
        flash_success: If True, flash success message
        flash_error: If True, flash error message

    Returns:
        Tuple of (success: bool, error_message: Optional[str])

    Example:
        >>> new_company = Company(name="Apple", ticker="AAPL")
        >>> success, error = safe_add_and_commit(
        ...     db.session,
        ...     new_company,
        ...     operation_name="Company creation",
        ...     flash_success=True
        ... )
    """
    try:
        db_session.add(obj)
        return safe_commit(
            db_session,
            operation_name,
            flash_success,
            flash_error
        )
    except Exception as e:
        db_session.rollback()
        error_msg = f"Error during {operation_name}: {str(e)}"
        logger.exception(error_msg)

        if flash_error:
            flash(error_msg, 'error')

        return False, error_msg


def safe_delete_and_commit(
    db_session,
    obj: Any,
    operation_name: str = "Delete",
    flash_success: bool = False,
    flash_error: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Delete object from session and commit with error handling.

    Args:
        db_session: SQLAlchemy database session
        obj: Object to delete
        operation_name: Name of the operation
        flash_success: If True, flash success message
        flash_error: If True, flash error message

    Returns:
        Tuple of (success: bool, error_message: Optional[str])

    Example:
        >>> company = Company.query.get(123)
        >>> success, error = safe_delete_and_commit(
        ...     db.session,
        ...     company,
        ...     flash_success=True
        ... )
    """
    try:
        db_session.delete(obj)
        return safe_commit(
            db_session,
            operation_name,
            flash_success,
            flash_error
        )
    except Exception as e:
        db_session.rollback()
        error_msg = f"Error during {operation_name}: {str(e)}"
        logger.exception(error_msg)

        if flash_error:
            flash(error_msg, 'error')

        return False, error_msg


def execute_with_retry(
    db_session,
    operation: Callable,
    max_retries: int = 3,
    operation_name: str = "Database operation"
) -> Tuple[bool, Optional[Any], Optional[str]]:
    """
    Execute database operation with retry logic.

    Args:
        db_session: SQLAlchemy database session
        operation: Callable that performs the database operation
        max_retries: Maximum number of retry attempts
        operation_name: Name of the operation for logging

    Returns:
        Tuple of (success: bool, result: Any, error_message: Optional[str])

    Example:
        >>> def create_user():
        ...     user = User(name="John")
        ...     db.session.add(user)
        ...     db.session.commit()
        ...     return user
        >>>
        >>> success, user, error = execute_with_retry(
        ...     db.session,
        ...     create_user,
        ...     max_retries=3
        ... )
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            result = operation()
            logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
            return True, result, None

        except Exception as e:
            last_error = str(e)
            db_session.rollback()
            logger.warning(
                f"{operation_name} failed on attempt {attempt + 1}/{max_retries}: {e}"
            )

            if attempt == max_retries - 1:
                logger.error(f"{operation_name} failed after {max_retries} attempts")

    return False, None, f"Operation failed after {max_retries} attempts: {last_error}"


def bulk_insert_with_error_handling(
    db_session,
    objects: list,
    operation_name: str = "Bulk insert"
) -> Tuple[int, int, list]:
    """
    Bulk insert objects with individual error handling.

    Args:
        db_session: SQLAlchemy database session
        objects: List of objects to insert
        operation_name: Name of the operation for logging

    Returns:
        Tuple of (success_count: int, error_count: int, errors: list)

    Example:
        >>> companies = [
        ...     Company(name="Apple", ticker="AAPL"),
        ...     Company(name="Google", ticker="GOOGL")
        ... ]
        >>> success_count, error_count, errors = bulk_insert_with_error_handling(
        ...     db.session,
        ...     companies
        ... )
        >>> print(f"Inserted {success_count} companies, {error_count} errors")
    """
    success_count = 0
    error_count = 0
    errors = []

    for obj in objects:
        try:
            db_session.add(obj)
            db_session.commit()
            success_count += 1
        except Exception as e:
            db_session.rollback()
            error_count += 1
            errors.append({
                'object': str(obj),
                'error': str(e)
            })
            logger.warning(f"Failed to insert object: {e}")

    logger.info(
        f"{operation_name} completed: {success_count} succeeded, {error_count} failed"
    )

    return success_count, error_count, errors


def get_or_create(
    db_session,
    model_class,
    defaults: Optional[dict] = None,
    **kwargs
) -> Tuple[Any, bool]:
    """
    Get existing object or create new one.

    Args:
        db_session: SQLAlchemy database session
        model_class: SQLAlchemy model class
        defaults: Dictionary of default values for new object
        **kwargs: Filter parameters to find existing object

    Returns:
        Tuple of (object, created: bool)

    Example:
        >>> company, created = get_or_create(
        ...     db.session,
        ...     Company,
        ...     defaults={'exchange': 'NASDAQ'},
        ...     ticker='AAPL'
        ... )
        >>> if created:
        ...     print("New company created")
        ... else:
        ...     print("Existing company found")
    """
    instance = model_class.query.filter_by(**kwargs).first()

    if instance:
        return instance, False
    else:
        if defaults is None:
            defaults = {}

        params = dict(kwargs)
        params.update(defaults)

        instance = model_class(**params)
        db_session.add(instance)
        db_session.commit()

        return instance, True


def count_total_records(model_class, user_id: Optional[int] = None) -> int:
    """
    Count total records for a model, optionally filtered by user.

    Args:
        model_class: SQLAlchemy model class
        user_id: Optional user ID to filter by

    Returns:
        Total count of records

    Example:
        >>> total_companies = count_total_records(Company, user_id=current_user.id)
        >>> print(f"You have {total_companies} companies")
    """
    query = model_class.query

    if user_id is not None:
        query = query.filter_by(user_id=user_id)

    return query.count()
