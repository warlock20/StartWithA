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
Domain catalog — a short, hand-written description of the user-facing data.

It covers the entities a user deals with, named the way the UI names them, not
the ~124 tables. The text lives in ``companion/domain_catalog.yaml``. It is
rendered whole into the companion prompt: at about 2k tokens it fits and can be
cached, and retrieving only part of it would let the agent wrongly conclude a
kind of record doesn't exist.

The same structure is the allowlist for ``query_my_data``, so it is precise
about two things a query needs:

- **Ownership.** Each entity says how a row reaches ``user_id``: on the row
  itself, or through relationships (a checklist answer is the user's through its
  run). A query can only reach rows along that path.
- **Derived fields.** Values like research duration are declared as an operation
  over catalogued columns (``{derived: date_diff_days, from: created_at, to:
  decision_date}``) and computed in SQL by ``derived_expression``, so the model
  never does date arithmetic itself.

``load_catalog`` checks the structure and raises on a malformed entry, because a
silently skipped entity would read to the agent as "you have none".
``find_drift`` checks the catalog against the code: tables, columns, types,
``values`` lists, owner paths and relations.
"""

import datetime
import decimal
import importlib
from dataclasses import dataclass

from sqlalchemy import Date, cast, inspect as sa_inspect

from app import db
from app import models
from app.services.ai.prompt_service import prompt_service

# Catalog type -> the Python type SQLAlchemy reports for a matching column.
FIELD_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'decimal': decimal.Decimal,
    'bool': bool,
    'date': datetime.date,
    'datetime': datetime.datetime,
}


def _date_diff_days(model, spec):
    # date - date is an integer number of days in Postgres, for Date and
    # DateTime columns alike once both are cast.
    return cast(getattr(model, spec['to']), Date) - cast(getattr(model, spec['from']), Date)


def _product(model, spec):
    expression = getattr(model, spec['of'][0])
    for name in spec['of'][1:]:
        expression = expression * getattr(model, name)
    return expression


# op -> (operand keys, how to read the operand field names, SQL builder)
DERIVED_OPS = {
    'date_diff_days': (('from', 'to'), lambda spec: [spec['from'], spec['to']], _date_diff_days),
    'product': (('of',), lambda spec: list(spec['of']), _product),
}


@dataclass(frozen=True)
class CatalogField:
    name: str
    type: str
    meaning: str = ''
    values: tuple = ()
    values_from: str = None
    derived: dict = None  # {'op': ..., plus the op's operand keys}

    @property
    def operands(self):
        """Column names a derived field is computed from; empty for a column."""
        if not self.derived:
            return []
        return DERIVED_OPS[self.derived['op']][1](self.derived)


@dataclass(frozen=True)
class CatalogEntity:
    key: str
    ui_name: str
    model: type
    description: str
    owner_through: tuple  # relationship names from this model to the owning one
    owner_column: str
    fields: dict  # name -> CatalogField
    relations: dict  # relationship name -> entity key


def _text(value):
    return ' '.join(str(value or '').split())


def _parse_field(where, name, raw):
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: field must be a mapping")
    field_type = raw.get('type')
    if field_type not in FIELD_TYPES:
        raise ValueError(f"{where}: type {field_type!r} is not one of {sorted(FIELD_TYPES)}")

    values = tuple(raw.get('values') or ())
    values_from = raw.get('values_from')
    if values and not values_from:
        raise ValueError(f"{where}: a values list needs values_from naming the constant it matches")
    if values_from and not values:
        raise ValueError(f"{where}: values_from without a values list")

    derived = None
    op = raw.get('derived')
    if op is not None:
        if op not in DERIVED_OPS:
            raise ValueError(f"{where}: derived op {op!r} is not one of {sorted(DERIVED_OPS)}")
        if values:
            raise ValueError(f"{where}: a derived field cannot have a values list")
        keys = DERIVED_OPS[op][0]
        missing = [k for k in keys if not raw.get(k)]
        if missing:
            raise ValueError(f"{where}: derived op {op!r} needs {missing}")
        derived = {'op': op, **{k: raw[k] for k in keys}}

    return CatalogField(
        name=name, type=field_type, meaning=_text(raw.get('meaning')),
        values=values, values_from=values_from, derived=derived)


def _parse_entity(key, raw):
    where = f"domain catalog entity {key!r}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be a mapping")
    for required in ('ui_name', 'model', 'description', 'owner', 'fields'):
        if not raw.get(required):
            raise ValueError(f"{where}: missing {required}")

    model = getattr(models, raw['model'], None)
    if not isinstance(model, type) or not issubclass(model, db.Model):
        raise ValueError(f"{where}: {raw['model']!r} is not a model exported by app.models")

    owner = raw['owner']
    if not isinstance(owner, dict) or not owner.get('column'):
        raise ValueError(f"{where}: owner needs a column")

    fields = {name: _parse_field(f"{where} field {name!r}", name, spec)
              for name, spec in raw['fields'].items()}
    for field in fields.values():
        for operand in field.operands:
            source = fields.get(operand)
            if source is None or source.derived:
                raise ValueError(
                    f"{where} field {field.name!r}: operand {operand!r} is not a catalogued column")

    return CatalogEntity(
        key=key, ui_name=_text(raw['ui_name']), model=model,
        description=_text(raw['description']),
        owner_through=tuple(owner.get('through') or ()), owner_column=owner['column'],
        fields=fields, relations=dict(raw.get('relations') or {}))


def load_catalog(data=None):
    """Parse the catalog into ``{entity key: CatalogEntity}``.

    ``data`` is the raw YAML mapping; by default it is read from
    ``companion/domain_catalog.yaml``. Raises ``ValueError`` on a malformed entry.
    """
    if data is None:
        data = prompt_service.get_prompt_data('companion', 'domain_catalog')
    raw_entities = (data or {}).get('entities')
    if not raw_entities:
        raise ValueError("domain catalog has no entities")

    catalog = {key: _parse_entity(key, raw) for key, raw in raw_entities.items()}
    for entity in catalog.values():
        for relation, target in entity.relations.items():
            if target not in catalog:
                raise ValueError(
                    f"domain catalog entity {entity.key!r} relation {relation!r}: "
                    f"{target!r} is not a catalogued entity")
    return catalog


def derived_expression(entity, field_name):
    """SQL expression for a derived field of ``entity``."""
    field = entity.fields[field_name]
    return DERIVED_OPS[field.derived['op']][2](entity.model, field.derived)


def _describe_derived(field):
    spec = field.derived
    if spec['op'] == 'date_diff_days':
        return f"{spec['to']} - {spec['from']}, in days"
    return ' x '.join(spec['of'])


def render_catalog(catalog=None):
    """The catalog as a compact text block for the prompt.

    Ownership and ``values_from`` are left out: the server enforces the first
    and the second only matters to the drift test.
    """
    catalog = catalog if catalog is not None else load_catalog()
    lines = []
    for entity in catalog.values():
        lines.append(f"{entity.key} — \"{entity.ui_name}\": {entity.description}")
        for field in entity.fields.values():
            detail = field.type
            if field.derived:
                detail += f", derived ({_describe_derived(field)})"
            if field.values:
                detail += ", one of " + " | ".join(field.values)
            line = f"  - {field.name} ({detail})"
            if field.meaning:
                line += f": {field.meaning}"
            lines.append(line)
        if entity.relations:
            links = ', '.join(f"{name} → {target}" for name, target in entity.relations.items())
            lines.append(f"  links: {links}")
    return "\n".join(lines)


def _import_constant(dotted):
    module_name, _, attr = dotted.rpartition('.')
    try:
        return getattr(importlib.import_module(module_name), attr)
    except (ImportError, AttributeError, ValueError):
        return None


def _column_python_type(column):
    try:
        return column.type.python_type
    except NotImplementedError:
        return None


def _find_field_drift(entity, field, table):
    where = f"{entity.key}.{field.name}"
    if field.derived:
        return []  # its operands are catalogued columns, checked on their own
    if field.name not in table.columns:
        return [f"{where}: no column {field.name!r} on table {table.name!r}"]
    if field.name not in sa_inspect(entity.model).column_attrs:
        return [f"{where}: {entity.model.__name__} has no column attribute {field.name!r}"]

    problems = []
    expected = FIELD_TYPES[field.type]
    actual = _column_python_type(table.columns[field.name])
    if actual is not None and actual is not expected:
        problems.append(f"{where}: declared {field.type} but the column holds {actual.__name__}")

    if field.values_from:
        constant = _import_constant(field.values_from)
        if constant is None:
            problems.append(f"{where}: values_from {field.values_from!r} does not import")
        elif set(field.values) != set(constant):
            problems.append(
                f"{where}: values {sorted(field.values)} do not match "
                f"{field.values_from} {sorted(constant)}")
    return problems


def _find_owner_drift(entity):
    where = f"{entity.key} owner"
    model = entity.model
    for hop in entity.owner_through:
        relationship = sa_inspect(model).relationships.get(hop)
        if relationship is None:
            return [f"{where}: {model.__name__} has no relationship {hop!r}"]
        if relationship.uselist:
            return [f"{where}: {model.__name__}.{hop} leads to many rows, so it cannot carry ownership"]
        model = relationship.mapper.class_

    column = model.__table__.columns.get(entity.owner_column)
    if column is None:
        return [f"{where}: {model.__name__} has no column {entity.owner_column!r}"]
    if not any(fk.target_fullname == 'user.id' for fk in column.foreign_keys):
        return [f"{where}: {model.__name__}.{entity.owner_column} is not a foreign key to user.id"]
    return []


def _find_relation_drift(entity, catalog):
    problems = []
    relationships = sa_inspect(entity.model).relationships
    for name, target in entity.relations.items():
        relationship = relationships.get(name)
        if relationship is None:
            problems.append(f"{entity.key} relation {name!r}: "
                            f"{entity.model.__name__} has no relationship {name!r}")
        elif relationship.mapper.class_ is not catalog[target].model:
            problems.append(
                f"{entity.key} relation {name!r}: leads to {relationship.mapper.class_.__name__}, "
                f"not {target} ({catalog[target].model.__name__})")
    return problems


def find_drift(catalog=None):
    """Where the catalog no longer matches the code, as readable problem lines.

    Empty means every catalogued table, column, type, values list, owner path
    and relation still exists as described.
    """
    catalog = catalog if catalog is not None else load_catalog()
    problems = []
    for entity in catalog.values():
        table = db.metadata.tables.get(entity.model.__tablename__)
        if table is None:
            problems.append(f"{entity.key}: table {entity.model.__tablename__!r} is not in db.metadata")
            continue
        for field in entity.fields.values():
            problems.extend(_find_field_drift(entity, field, table))
        problems.extend(_find_owner_drift(entity))
        problems.extend(_find_relation_drift(entity, catalog))
    return problems
