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

"""Competitor links between a user's companies.

A link is stored once, in one direction (`Company.competitors` / its backref
`competed_by`), but competition is mutual: if ASML lists Canon as a competitor,
Canon's page should list ASML too. Everything that reads or changes the links
goes through here so both directions are always considered together.
"""

from sqlalchemy import and_, or_, select

from app import db
from app.models import Company, competitors_association

_assoc = competitors_association.c


def _pair_clause(company_id, other_id):
    """Match the association row(s) linking the two companies, either direction."""
    return or_(
        and_(_assoc.company_id == company_id, _assoc.competitor_id == other_id),
        and_(_assoc.company_id == other_id, _assoc.competitor_id == company_id),
    )


def list_competitors(company):
    """Companies linked to `company` in either direction, de-duplicated, by name.

    Scoped to the company's owner, so a stray cross-user link can never surface
    someone else's company.
    """
    linked_ids = select(_assoc.competitor_id).where(_assoc.company_id == company.id).union(
        select(_assoc.company_id).where(_assoc.competitor_id == company.id)
    )
    return Company.query.filter(
        Company.id.in_(linked_ids),
        Company.user_id == company.user_id,
    ).order_by(Company.name).all()


def are_competitors(company_id, other_id):
    """True if the two companies are linked in either direction."""
    return db.session.execute(
        select(_assoc.company_id).where(_pair_clause(company_id, other_id)).limit(1)
    ).first() is not None


def link_competitors(company, competitor):
    """Record `competitor` as a competitor of `company` (one row, one direction).

    Returns False without writing if the pair is already linked either way.
    The caller commits.
    """
    if are_competitors(company.id, competitor.id):
        return False
    company.competitors.append(competitor)
    return True


def unlink_competitors(company_id, other_id):
    """Delete the link between the two companies, whichever direction it was stored in.

    Returns the number of association rows removed. The caller commits.
    """
    result = db.session.execute(
        competitors_association.delete().where(_pair_clause(company_id, other_id))
    )
    return result.rowcount
