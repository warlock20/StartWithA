"""
Calculation Utilities
Common mathematical calculations and statistical functions.
"""

from typing import List, Union, Optional, Any, Callable
from decimal import Decimal


def safe_divide(
    numerator: Union[int, float, Decimal],
    denominator: Union[int, float, Decimal],
    default: Union[int, float] = 0.0,
    precision: Optional[int] = None
) -> Union[int, float]:
    """
    Safely divide two numbers with zero-division handling.

    Args:
        numerator: The numerator
        denominator: The denominator
        default: Value to return if denominator is zero
        precision: Number of decimal places to round to (None = no rounding)

    Returns:
        Result of division or default value

    Example:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide(10, 3, precision=2)
        3.33
    """
    if denominator == 0:
        return default

    result = numerator / denominator

    if precision is not None:
        return round(result, precision)

    return result


def calculate_average(
    values: List[Union[int, float, Decimal]],
    default: float = 0.0,
    precision: int = 2,
    skip_none: bool = True
) -> float:
    """
    Calculate average of a list of numbers with safe handling.

    Args:
        values: List of numeric values
        default: Value to return if list is empty
        precision: Number of decimal places to round to
        skip_none: If True, skip None values in calculation

    Returns:
        Average value rounded to specified precision

    Example:
        >>> calculate_average([10, 20, 30])
        20.0
        >>> calculate_average([10, None, 30], skip_none=True)
        20.0
        >>> calculate_average([])
        0.0
        >>> calculate_average([1, 2, 3], precision=1)
        2.0
    """
    if not values:
        return default

    if skip_none:
        values = [v for v in values if v is not None]

    if not values:
        return default

    return round(sum(values) / len(values), precision)


def calculate_average_from_objects(
    objects: List[Any],
    field_name: str,
    default: float = 0.0,
    precision: int = 1,
    fallback_value: Union[int, float] = 0
) -> float:
    """
    Calculate average of a specific field from a list of objects.

    Args:
        objects: List of objects
        field_name: Name of the attribute to average
        default: Value to return if no valid values found
        precision: Number of decimal places to round to
        fallback_value: Value to use if attribute is None

    Returns:
        Average value of the specified field

    Example:
        >>> users = [User(age=25), User(age=30), User(age=None)]
        >>> calculate_average_from_objects(users, 'age', fallback_value=0)
        18.3
    """
    if not objects:
        return default

    values = [
        getattr(obj, field_name, None) or fallback_value
        for obj in objects
        if hasattr(obj, field_name)
    ]

    return calculate_average(values, default, precision)


def calculate_percentage(
    part: Union[int, float],
    total: Union[int, float],
    default: float = 0.0,
    precision: int = 1
) -> float:
    """
    Calculate percentage with safe division.

    Args:
        part: The part value
        total: The total value
        default: Value to return if total is zero
        precision: Number of decimal places to round to

    Returns:
        Percentage value

    Example:
        >>> calculate_percentage(25, 100)
        25.0
        >>> calculate_percentage(1, 3, precision=2)
        33.33
        >>> calculate_percentage(10, 0)
        0.0
    """
    if total == 0:
        return default

    return round((part / total) * 100, precision)


def calculate_win_rate_from_list(
    items: List[Any],
    is_winner_fn: Callable[[Any], bool],
    precision: int = 1
) -> float:
    """
    Calculate win rate from a list using a custom predicate.

    Args:
        items: List of items to analyze
        is_winner_fn: Function that returns True if item is a "winner"
        precision: Number of decimal places to round to

    Returns:
        Win rate as percentage

    Example:
        >>> trades = [Trade(profit=100), Trade(profit=-50), Trade(profit=75)]
        >>> calculate_win_rate_from_list(trades, lambda t: t.profit > 0)
        66.7
    """
    if not items:
        return 0.0

    winners = sum(1 for item in items if is_winner_fn(item))
    return calculate_percentage(winners, len(items), precision=precision)


def sum_from_objects(
    objects: List[Any],
    field_name: str,
    default_value: Union[int, float] = 0
) -> Union[int, float]:
    """
    Sum a specific field from a list of objects.

    Args:
        objects: List of objects
        field_name: Name of the attribute to sum
        default_value: Value to use if attribute is None

    Returns:
        Sum of the field values

    Example:
        >>> orders = [Order(total=100), Order(total=200), Order(total=None)]
        >>> sum_from_objects(orders, 'total', default_value=0)
        300
    """
    if not objects:
        return 0

    return sum(
        getattr(obj, field_name, None) or default_value
        for obj in objects
        if hasattr(obj, field_name)
    )


def count_matching(
    items: List[Any],
    predicate: Callable[[Any], bool]
) -> int:
    """
    Count items matching a predicate.

    Args:
        items: List of items to count
        predicate: Function that returns True for items to count

    Returns:
        Count of matching items

    Example:
        >>> users = [User(active=True), User(active=False), User(active=True)]
        >>> count_matching(users, lambda u: u.active)
        2
    """
    if not items:
        return 0

    return sum(1 for item in items if predicate(item))


def filter_and_count(
    items: List[Any],
    predicate: Callable[[Any], bool]
) -> tuple[int, List[Any]]:
    """
    Filter items and return both count and filtered list in one pass.

    Args:
        items: List of items to filter
        predicate: Function that returns True for items to keep

    Returns:
        Tuple of (count, filtered_list)

    Example:
        >>> users = [User(age=25), User(age=17), User(age=30)]
        >>> count, adults = filter_and_count(users, lambda u: u.age >= 18)
        >>> count
        2
    """
    if not items:
        return 0, []

    filtered = [item for item in items if predicate(item)]
    return len(filtered), filtered


def calculate_growth_rate(
    old_value: Union[int, float],
    new_value: Union[int, float],
    precision: int = 1
) -> float:
    """
    Calculate growth rate percentage.

    Args:
        old_value: Original value
        new_value: New value
        precision: Number of decimal places to round to

    Returns:
        Growth rate as percentage

    Example:
        >>> calculate_growth_rate(100, 150)
        50.0
        >>> calculate_growth_rate(200, 150)
        -25.0
    """
    if old_value == 0:
        return 0.0

    return round(((new_value - old_value) / old_value) * 100, precision)


def weighted_average(
    values: List[Union[int, float]],
    weights: List[Union[int, float]],
    default: float = 0.0,
    precision: int = 2
) -> float:
    """
    Calculate weighted average.

    Args:
        values: List of values
        weights: List of weights (must be same length as values)
        default: Value to return if lists are empty or lengths don't match
        precision: Number of decimal places to round to

    Returns:
        Weighted average

    Example:
        >>> weighted_average([10, 20, 30], [1, 2, 3])
        23.33
    """
    if not values or not weights or len(values) != len(weights):
        return default

    total_weight = sum(weights)
    if total_weight == 0:
        return default

    weighted_sum = sum(v * w for v, w in zip(values, weights))
    return round(weighted_sum / total_weight, precision)


def calculate_median(
    values: List[Union[int, float]],
    default: float = 0.0
) -> float:
    """
    Calculate median value.

    Args:
        values: List of numeric values
        default: Value to return if list is empty

    Returns:
        Median value

    Example:
        >>> calculate_median([1, 2, 3, 4, 5])
        3.0
        >>> calculate_median([1, 2, 3, 4])
        2.5
    """
    if not values:
        return default

    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2

    if n % 2 == 0:
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2
    else:
        return float(sorted_values[mid])
