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
Structured, ownership-scoped aggregate queries over the domain catalog.

Backs the companion's ``query_my_data`` tool. The model sends a JSON spec, never
SQL; the server builds the query:

    {"entity": "checklist_answer",
     "group_by": ["item.text", "satisfaction_status"],
     "aggregates": [{"op": "count"}],
     "filters": [{"field": "answered_at", "op": "gte", "value": "2026-01-01"}],
     "order_by": [{"by": "count", "dir": "desc"}],
     "limit": 20}

- **The catalog is the allowlist.** Entities, fields (plus an implicit ``id``)
  and the relations a path may join through come from ``load_catalog``; anything
  else, ``user_id`` included, is a ``QueryError`` that names the valid choices so
  the model can correct itself.
- **Ownership is applied to every table in the query.** Each entity is an
  ``aliased()`` table with its own predicate built from the catalog's owner path.
  The base entity's goes in WHERE. A joined entity's goes in its LEFT JOIN's ON
  clause, so a related row that isn't the user's comes back as nulls: it is never
  shown, and it doesn't drop the row that points at it. Aliasing everything also
  keeps the owner path's EXISTS subqueries from correlating to an outer table.
- **Read-only, time-limited, row-limited.** The query runs in a savepoint set to
  READ ONLY with a ``statement_timeout``, and the savepoint is always rolled back.
  A savepoint rather than a separate connection, so the query sees the request's
  own session state.
"""

import datetime
import decimal

from sqlalchemy import Date, Numeric, and_, cast, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import aliased

from app import db
from app.services.argos.domain_catalog import CatalogField, derived_expression, load_catalog

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_JOIN_DEPTH = 3
QUERY_TIMEOUT_MS = 3000

SPEC_KEYS = ('entity', 'fields', 'group_by', 'aggregates', 'filters', 'order_by', 'limit')

NUMERIC_TYPES = {'int', 'float', 'decimal'}
TEMPORAL_TYPES = {'date', 'datetime'}

# op -> catalog field types it accepts (None: count, which takes any field or none)
AGGREGATE_OPS = {
    'count': None,
    'sum': NUMERIC_TYPES,
    'avg': NUMERIC_TYPES,
    'median': NUMERIC_TYPES,
    'min': NUMERIC_TYPES | TEMPORAL_TYPES,
    'max': NUMERIC_TYPES | TEMPORAL_TYPES,
}

COMPARISONS = {
    'eq': lambda a, b: a == b,
    'ne': lambda a, b: a != b,
    'lt': lambda a, b: a < b,
    'lte': lambda a, b: a <= b,
    'gt': lambda a, b: a > b,
    'gte': lambda a, b: a >= b,
}
ORDERED_COMPARISONS = {'lt', 'lte', 'gt', 'gte'}
FILTER_OPS = (*COMPARISONS, 'in', 'is_null', 'not_null', 'contains')

# Postgres SQLSTATE for a statement cancelled by statement_timeout.
_QUERY_CANCELED = '57014'

ID_FIELD = CatalogField(name='id', type='int', meaning='The record id')


class QueryError(ValueError):
    """A spec the catalog doesn't allow, worded for the model to correct."""


def _family(field_type):
    if field_type in NUMERIC_TYPES:
        return 'number'
    if field_type in TEMPORAL_TYPES:
        return 'date'
    return field_type


def _owner_condition(entity, alias, user_id):
    """``alias``'s rows that belong to ``user_id``, along the catalog owner path."""
    models = [alias]
    model = entity.model
    for hop in entity.owner_through:
        model = sa_inspect(model).relationships[hop].mapper.class_
        models.append(model)
    condition = getattr(models[-1], entity.owner_column) == user_id
    for hop, model in zip(reversed(entity.owner_through), reversed(models[:-1])):
        condition = getattr(model, hop).has(condition)
    return condition


class _Query:
    """One spec being resolved into a statement for one user."""

    def __init__(self, user_id, catalog, entity_key):
        if entity_key not in catalog:
            raise QueryError(f"unknown entity {entity_key!r}; entities: {', '.join(catalog)}")
        self.user_id = user_id
        self.catalog = catalog
        self.entity = catalog[entity_key]
        self.alias = aliased(self.entity.model)
        self._joined = {}  # relation path tuple -> (entity, alias)
        self.joins = []  # ON-clause targets, in the order they were first needed

    def resolve(self, path):
        """``(SQL expression, CatalogField)`` for a dotted field path."""
        if not isinstance(path, str) or not path.strip():
            raise QueryError(f"a field path must be a non-empty string, got {path!r}")
        *hops, name = path.strip().split('.')
        if len(hops) > MAX_JOIN_DEPTH:
            raise QueryError(f"{path!r} joins {len(hops)} relations; at most {MAX_JOIN_DEPTH}")

        entity, alias = self.entity, self.alias
        for depth, hop in enumerate(hops):
            if hop not in entity.relations:
                raise QueryError(
                    f"{entity.key} has no relation {hop!r} (in {path!r}); "
                    f"relations: {', '.join(entity.relations) or 'none'}")
            key = tuple(hops[:depth + 1])
            if key not in self._joined:
                target = self.catalog[entity.relations[hop]]
                target_alias = aliased(target.model)
                self.joins.append(getattr(alias, hop).of_type(target_alias).and_(
                    _owner_condition(target, target_alias, self.user_id)))
                self._joined[key] = (target, target_alias)
            entity, alias = self._joined[key]

        if name == 'id':
            return alias.id, ID_FIELD
        field = entity.fields.get(name)
        if field is None:
            raise QueryError(
                f"unknown field {name!r} on {entity.key}; fields: "
                f"{', '.join(sorted([*entity.fields, 'id']))}; "
                f"relations: {', '.join(entity.relations) or 'none'}")
        if field.derived:
            return derived_expression(entity, name, alias), field
        return getattr(alias, name), field

    def owner_condition(self):
        return _owner_condition(self.entity, self.alias, self.user_id)


# =========================================================================
# Values
# =========================================================================

def _parse_value(field, path, value):
    """``value`` as the Python type of ``field``; strings are parsed."""
    def bad(expected):
        return QueryError(f"{path}: {value!r} is not {expected}")

    if value is None or isinstance(value, (dict, list)):
        raise bad(f"a {field.type} value (use is_null / not_null for empty)")

    if field.type == 'str':
        value = str(value)
        if field.values and value not in field.values:
            raise QueryError(f"{path}: {value!r} is not one of {', '.join(field.values)}")
        return value
    if field.type == 'bool':
        if isinstance(value, bool):
            return value
        if str(value).strip().lower() in ('true', 'false'):
            return str(value).strip().lower() == 'true'
        raise bad('true or false')
    if isinstance(value, bool):
        raise bad(f"a {field.type}")
    if field.type == 'int':
        try:
            number = decimal.Decimal(str(value).strip())
        except decimal.InvalidOperation:
            raise bad('a whole number') from None
        if number != number.to_integral_value():
            raise bad('a whole number')
        return int(number)
    if field.type in ('float', 'decimal'):
        try:
            number = decimal.Decimal(str(value).strip())
        except decimal.InvalidOperation:
            raise bad('a number') from None
        if not number.is_finite():
            raise bad('a number')
        return float(number) if field.type == 'float' else number
    if field.type in TEMPORAL_TYPES:
        try:
            moment = datetime.datetime.fromisoformat(str(value).strip())
        except ValueError:
            raise bad('an ISO date like 2026-01-31') from None
        if moment.tzinfo is not None:
            # Stored timestamps are naive UTC.
            moment = moment.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return moment.date() if field.type == 'date' else moment
    raise bad(f"a {field.type}")


# =========================================================================
# Spec parts
# =========================================================================

def _string_list(spec, key):
    value = spec.get(key) or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise QueryError(f"{key} must be a list")
    return value


def _object_list(spec, key):
    value = spec.get(key) or []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise QueryError(f"{key} must be a list of objects")
    return value


def _filter_condition(query, raw):
    if not isinstance(raw, dict):
        raise QueryError(f"each filter must be an object, got {raw!r}")
    path = raw.get('field')
    op = raw.get('op')
    expression, field = query.resolve(path)
    if op not in FILTER_OPS:
        raise QueryError(f"filter on {path}: unknown op {op!r}; ops: {', '.join(FILTER_OPS)}")

    if op == 'is_null':
        return expression.is_(None)
    if op == 'not_null':
        return expression.is_not(None)

    if op in ORDERED_COMPARISONS and _family(field.type) not in ('number', 'date'):
        raise QueryError(f"filter on {path}: {op} needs a number or date field, not {field.type}")

    if op == 'contains':
        if field.type != 'str' or field.values:
            raise QueryError(
                f"filter on {path}: contains is for free-text fields; "
                f"use eq or in for a field with listed values")
        return expression.icontains(_parse_value(field, path, raw.get('value')), autoescape=True)

    if op == 'in':
        values = raw.get('values', raw.get('value'))
        if not isinstance(values, list) or not values:
            raise QueryError(f"filter on {path}: in needs a non-empty values list")
        return expression.in_([_parse_value(field, path, v) for v in values])

    other_path = raw.get('other_field')
    if other_path is not None:
        other, other_field = query.resolve(other_path)
        if _family(field.type) != _family(other_field.type):
            raise QueryError(
                f"filter {path} {op} {other_path}: cannot compare {field.type} with {other_field.type}")
        if field.type != other_field.type and _family(field.type) == 'date':
            # A date against a timestamp compares calendar days, so a buy on the
            # day research finished is not "before" it.
            expression, other = cast(expression, Date), cast(other, Date)
        return COMPARISONS[op](expression, other)

    return COMPARISONS[op](expression, _parse_value(field, path, raw.get('value')))


def _aggregate_name(raw):
    """Result column name: ``count``, ``count(f)``, ``avg(research_days)``."""
    if isinstance(raw, str):
        return raw
    op, path = raw.get('op'), raw.get('field')
    return f"{op}({path})" if path else str(op)


def _aggregate_expression(query, raw):
    if isinstance(raw, str):
        raw = {'op': raw}
    if not isinstance(raw, dict):
        raise QueryError(f"each aggregate must be an object like {{\"op\": \"count\"}}, got {raw!r}")
    op, path = raw.get('op'), raw.get('field')
    if op not in AGGREGATE_OPS:
        raise QueryError(f"unknown aggregate op {op!r}; ops: {', '.join(AGGREGATE_OPS)}")
    if op == 'count':
        return func.count(query.resolve(path)[0]) if path else func.count()
    if not path:
        raise QueryError(f"aggregate {op} needs a field")
    expression, field = query.resolve(path)
    if field.type not in AGGREGATE_OPS[op]:
        raise QueryError(f"aggregate {op}({path}): {path} is {field.type}, "
                         f"{op} needs {' or '.join(sorted(AGGREGATE_OPS[op]))}")
    if op == 'avg':
        return func.round(cast(func.avg(expression), Numeric), 2)
    if op == 'median':
        return func.round(cast(func.percentile_cont(0.5).within_group(expression), Numeric), 2)
    return getattr(func, op)(expression)


def _limit(spec):
    raw = spec.get('limit')
    if raw is None:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        raise QueryError(f"limit must be a whole number, got {raw!r}") from None
    return max(1, min(limit, MAX_LIMIT))


def _order(columns, raw_order, default):
    """ORDER BY terms. ``columns`` maps each orderable name to its expression."""
    terms = []
    for raw in raw_order:
        by = raw.get('by') if isinstance(raw, dict) else raw
        if not isinstance(by, str) or by not in columns:
            raise QueryError(f"cannot order by {by!r}; choose from: {', '.join(columns)}")
        direction = str(raw.get('dir') or 'asc').lower()
        if direction not in ('asc', 'desc'):
            raise QueryError(f"order dir must be asc or desc, got {raw.get('dir')!r}")
        expression = columns[raw['by']]
        terms.append((expression.desc() if direction == 'desc' else expression.asc()).nulls_last())
    return terms or default


# =========================================================================
# Running
# =========================================================================

def execute_read_only(statement):
    """Run ``statement`` in a READ ONLY savepoint with a statement timeout.

    The savepoint is always rolled back, which also restores the session's
    read-write mode and timeout for whatever the request does next.
    """
    savepoint = db.session.begin_nested()
    try:
        db.session.execute(text('SET TRANSACTION READ ONLY'))
        db.session.execute(text(f'SET LOCAL statement_timeout = {int(QUERY_TIMEOUT_MS)}'))
        return db.session.execute(statement).all()
    except OperationalError as e:
        if getattr(e.orig, 'pgcode', None) == _QUERY_CANCELED:
            raise QueryError(
                f"the query took longer than {QUERY_TIMEOUT_MS / 1000:g}s; "
                f"narrow it with filters") from e
        raise
    finally:
        savepoint.rollback()


def _build(user_id, spec, catalog):
    if not isinstance(spec, dict):
        raise QueryError("the query must be an object")
    unknown = sorted(set(spec) - set(SPEC_KEYS))
    if unknown:
        raise QueryError(f"unknown query keys {unknown}; keys: {', '.join(SPEC_KEYS)}")

    query = _Query(user_id, catalog, spec.get('entity'))
    conditions = [query.owner_condition()]
    conditions += [_filter_condition(query, raw) for raw in _object_list(spec, 'filters')]

    group_by = _string_list(spec, 'group_by')
    raw_aggregates = _object_list(spec, 'aggregates')
    order_by = _object_list(spec, 'order_by')

    if group_by or raw_aggregates:
        if spec.get('fields'):
            raise QueryError("fields is for row queries; with aggregates, use group_by")
        raw_aggregates = raw_aggregates or [{'op': 'count'}]
        groups = [(path, query.resolve(path)[0]) for path in group_by]
        aggregates = [(_aggregate_name(raw), _aggregate_expression(query, raw))
                      for raw in raw_aggregates]
        names = [name for name, _ in groups + aggregates]
        if len(set(names)) != len(names):
            raise QueryError(f"duplicate result columns in {names}")
        columns = dict(groups + aggregates)
        default_order = [aggregates[0][1].desc().nulls_last()]
        default_order += [expression.asc().nulls_last() for _, expression in groups]
        statement = select(*[expression.label(name) for name, expression in groups + aggregates])
        statement = statement.group_by(*[expression for _, expression in groups])
    else:
        paths = _string_list(spec, 'fields') or ['id', *query.entity.fields]
        if len(set(paths)) != len(paths):
            raise QueryError(f"duplicate fields in {paths}")
        columns = {path: query.resolve(path)[0] for path in paths}
        for raw in order_by:
            # Rows can be ordered by any field, shown or not.
            if isinstance(raw, dict) and isinstance(raw.get('by'), str) and raw['by'] not in columns:
                columns[raw['by']] = query.resolve(raw['by'])[0]
        names = paths
        default_order = [query.alias.id.desc()]
        statement = select(*[columns[path].label(path) for path in paths])

    statement = statement.order_by(*_order(columns, order_by, default_order))
    statement = statement.select_from(query.alias)
    for join in query.joins:
        statement = statement.outerjoin(join)
    return statement.where(and_(*conditions)), names


def run_query(user_id, spec, catalog=None):
    """Run a ``query_my_data`` spec for ``user_id``.

    Returns ``{'entity', 'columns', 'rows': [{column: value}], 'truncated'}``.
    Raises ``QueryError`` when the spec isn't allowed by the catalog.
    """
    catalog = catalog if catalog is not None else load_catalog()
    statement, names = _build(user_id, spec, catalog)
    limit = _limit(spec)
    rows = execute_read_only(statement.limit(limit + 1))
    return {
        'entity': spec['entity'],
        'columns': names,
        'rows': [dict(zip(names, row)) for row in rows[:limit]],
        'truncated': len(rows) > limit,
    }


def describe_query(spec, catalog=None):
    """A one-line label for a spec, for its citation card."""
    catalog = catalog if catalog is not None else load_catalog()
    entity = catalog.get(spec.get('entity'))
    name = entity.ui_name if entity else str(spec.get('entity'))
    group_by = _string_list(spec, 'group_by')
    aggregates = _object_list(spec, 'aggregates')
    if not (group_by or aggregates):
        return f"{name}: records"
    label = f"{name}: {', '.join(_aggregate_name(a) for a in aggregates) or 'count'}"
    if group_by:
        label += f" by {', '.join(group_by)}"
    return label
