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
Which company a market-sweep row is, for one user.

A sweep row is shared by every user; a company belongs to one. Resolving the
two is a judgement, so it is stored once and read thereafter -- never
recomputed. Step 3's company_state() then answers what the user thinks of the
company the link points at.
"""

import logging

from app import db
from app.models.company import Company
from app.models.idea_pipeline import IdeaPipeline
from app.models.market_sweep import (
    CompanySweepLink, MarketSweepCompany, MarketSweepDecision,
)
from app.utils.company_identity import normalize_company_name

logger = logging.getLogger(__name__)


def link_for(user_id, sweep_company_id):
    """The stored link for one sweep row, or None if it has never been made."""
    return CompanySweepLink.query.filter_by(
        user_id=user_id, sweep_company_id=sweep_company_id,
    ).first()


def links_for(user_id, sweep_id):
    """Every link this user has in one sweep.

    Returns {sweep_company_id: {'company_id': int, 'origin': str}}. One query,
    so rendering a sweep costs the same whether it has ten rows or ten
    thousand.

    origin travels with the company id because a caller that shows a link also
    has to say how it came to exist -- decided, matched, or confirmed -- and
    whether unlinking is on offer. Returning the id alone would force a second
    lookup per row and undo the point of the batch.
    """
    rows = db.session.query(
        CompanySweepLink.sweep_company_id,
        CompanySweepLink.company_id,
        CompanySweepLink.origin,
    ).join(
        MarketSweepCompany,
        MarketSweepCompany.id == CompanySweepLink.sweep_company_id,
    ).filter(
        CompanySweepLink.user_id == user_id,
        MarketSweepCompany.sweep_id == sweep_id,
    ).all()
    return {
        sweep_company_id: {'company_id': company_id, 'origin': origin}
        for sweep_company_id, company_id, origin in rows
    }


def link_from_decision(decision, commit=False):
    """Create the link a sweep decision already implies.

    Deciding on a row is itself the statement that the row is a particular
    company, so no matching is involved. Returns None when the decision carries
    no idea, or its idea no company -- there is nothing to point at.

    An existing link is left alone: a stored link is never re-derived.
    """
    if decision is None or not decision.promoted_idea_id:
        return None

    idea = IdeaPipeline.query.filter_by(
        id=decision.promoted_idea_id, user_id=decision.user_id,
    ).first()
    if idea is None or not idea.company_id:
        return None

    # The idea belongs to this user, but the company it names still has to.
    # Sweep rows are shared, so a link to someone else's company would publish
    # that company's state onto a row every user sees -- confirm() checks the
    # same thing before writing, and the backfill walks every user's decisions
    # at once, where an unchecked id has the whole database to go wrong in.
    owned = Company.query.filter_by(
        id=idea.company_id, user_id=decision.user_id,
    ).first()
    if owned is None:
        logger.warning(
            "Decision on sweep row %s names company %s, which does not belong "
            "to user %s. No link made.",
            decision.sweep_company_id, idea.company_id, decision.user_id,
        )
        return None

    existing = link_for(decision.user_id, decision.sweep_company_id)
    if existing is not None:
        return existing

    link = CompanySweepLink(
        user_id=decision.user_id,
        sweep_company_id=decision.sweep_company_id,
        company_id=idea.company_id,
        origin=CompanySweepLink.ORIGIN_DECISION,
    )
    db.session.add(link)
    db.session.flush()
    if commit:
        db.session.commit()
    return link


def backfill_decision_links(commit=False):
    """Materialise the link behind every decision that already has one.

    Idempotent: rows already linked are skipped, so a second run creates none.
    """
    created = 0
    for decision in MarketSweepDecision.query.all():
        before = link_for(decision.user_id, decision.sweep_company_id)
        if before is not None:
            continue
        if link_from_decision(decision) is not None:
            created += 1

    if commit:
        db.session.commit()
    logger.info("backfill_decision_links: created %d link(s)", created)
    return created


def _report_isin_conflict(row, existing, company):
    """Say out loud when an ISIN disagrees with a link that is already stored.

    The stored link stands -- a judgement already recorded is never rewritten
    by a rule. But skipping in silence hides a genuine disagreement about
    which company a row is, and the quiet version of that bug is the one
    nobody finds. So the conflict is logged and the link left alone.
    """
    if existing.company_id == company.id:
        return
    logger.warning(
        "ISIN %s on sweep row %s points at company %s, but user %s already has "
        "a %s link from that row to company %s. The stored link stands.",
        row.isin, row.id, company.id, existing.user_id, existing.origin,
        existing.company_id,
    )


def link_from_isin(user_id, isin, commit=False):
    """Link every sweep row carrying *isin* to this user's company with it.

    An ISIN identifies a security outright, so this needs no judgement and no
    threshold. It is also rare: most rows and most companies have none, which is
    why it supplements confirmation rather than replacing it.

    Rows already linked are left alone -- a stored link is never re-derived --
    and a link pointing somewhere else is reported rather than rewritten.
    """
    if not isin:
        return []

    company = Company.query.filter_by(user_id=user_id, isin=isin).first()
    if company is None:
        return []

    created = []
    for row in MarketSweepCompany.query.filter_by(isin=isin).all():
        existing = link_for(user_id, row.id)
        if existing is not None:
            _report_isin_conflict(row, existing, company)
            continue
        link = CompanySweepLink(
            user_id=user_id, sweep_company_id=row.id, company_id=company.id,
            origin=CompanySweepLink.ORIGIN_ISIN,
        )
        db.session.add(link)
        created.append(link)

    db.session.flush()
    if commit:
        db.session.commit()
    return created


def link_sweep_row_by_isin(sweep_company, commit=False):
    """Link one sweep row to every user who owns a company carrying its ISIN.

    The company-side counterpart, link_from_isin(), starts from one user's
    company and is right for that direction. This one starts from the row --
    and a row is global. An admin typing an ISIN onto it answers "which
    company is this" for every user at once, not only for whoever typed it,
    so linking only the acting user would leave everyone else's row blank on
    evidence that was equally theirs.

    Users with no company for that ISIN get nothing; rows already linked are
    left alone, and a link pointing elsewhere is reported rather than rewritten.
    """
    if sweep_company is None or not sweep_company.isin:
        return []

    created = []
    for company in Company.query.filter_by(isin=sweep_company.isin).all():
        existing = link_for(company.user_id, sweep_company.id)
        if existing is not None:
            _report_isin_conflict(sweep_company, existing, company)
            continue
        link = CompanySweepLink(
            user_id=company.user_id,
            sweep_company_id=sweep_company.id,
            company_id=company.id,
            origin=CompanySweepLink.ORIGIN_ISIN,
        )
        db.session.add(link)
        created.append(link)

    db.session.flush()
    if commit:
        db.session.commit()
    return created


def suggest(user_id, sweep_company_id):
    """Companies this row might be. Returns candidates; never stores anything.

    Name equivalence is a guess, and a wrong stored link is invisible precisely
    because it looks decided -- it marks a company reviewed that the user never
    saw. So matching proposes and a human disposes: the caller shows these and
    only confirm() writes.

    An already-linked row suggests nothing; its answer is settled.
    """
    if link_for(user_id, sweep_company_id) is not None:
        return []

    row = MarketSweepCompany.query.get(sweep_company_id)
    if row is None:
        return []

    hits = []

    if row.isin:
        for company in Company.query.filter_by(user_id=user_id, isin=row.isin).all():
            hits.append({'company_id': company.id, 'name': company.name,
                         'basis': 'isin'})

    normalized = normalize_company_name(row.company_name)
    if normalized:
        seen = {hit['company_id'] for hit in hits}
        for company in Company.query.filter_by(user_id=user_id).all():
            if company.id in seen:
                continue
            if normalize_company_name(company.name) == normalized:
                hits.append({'company_id': company.id, 'name': company.name,
                             'basis': 'name'})

    return hits


def suggestions_for(user_id, sweep_id):
    """suggest() for a whole sweep at once, as {sweep_company_id: [candidate]}.

    The batch peer of suggest(), exactly as links_for() is link_for()'s. Same
    candidates, same guarantee that nothing is written; the difference is cost.
    suggest() loads the user's companies and normalises every name once per
    row, which a page of rows pays for once per row. Here the index is built
    once and walked.

    Only unlinked rows are considered -- a linked row's answer is settled --
    and rows with no candidate are absent rather than mapped to an empty list.
    """
    rows = MarketSweepCompany.query.filter_by(sweep_id=sweep_id).all()
    if not rows:
        return {}

    linked = set(links_for(user_id, sweep_id))

    by_isin = {}
    by_name = {}
    for company in Company.query.filter_by(user_id=user_id).all():
        if company.isin:
            by_isin.setdefault(company.isin, []).append(company)
        normalized = normalize_company_name(company.name)
        if normalized:
            by_name.setdefault(normalized, []).append(company)

    out = {}
    for row in rows:
        if row.id in linked:
            continue

        hits = []
        seen = set()
        if row.isin:
            for company in by_isin.get(row.isin, ()):
                hits.append({'company_id': company.id, 'name': company.name,
                             'basis': 'isin'})
                seen.add(company.id)

        normalized = normalize_company_name(row.company_name)
        if normalized:
            for company in by_name.get(normalized, ()):
                if company.id in seen:
                    continue
                hits.append({'company_id': company.id, 'name': company.name,
                             'basis': 'name'})

        if hits:
            out[row.id] = hits

    return out


def confirm(user_id, sweep_company_id, company_id, commit=False):
    """Record a human's answer for this row.

    Replaces a link derived by machine, because a person looking at both rows
    knows more than a rule does. The reverse never happens: no automatic path
    overwrites a confirmed link.
    """
    company = Company.query.filter_by(id=company_id, user_id=user_id).first()
    if company is None:
        raise ValueError('That company does not belong to this user.')

    link = link_for(user_id, sweep_company_id)
    if link is None:
        link = CompanySweepLink(user_id=user_id, sweep_company_id=sweep_company_id)
        db.session.add(link)

    link.company_id = company_id
    link.origin = CompanySweepLink.ORIGIN_CONFIRMED

    db.session.flush()
    if commit:
        db.session.commit()
    return link


def unlink(user_id, sweep_company_id, commit=False):
    """Forget which company this row is. True if a link was removed."""
    link = link_for(user_id, sweep_company_id)
    if link is None:
        return False

    db.session.delete(link)
    db.session.flush()
    if commit:
        db.session.commit()
    return True
