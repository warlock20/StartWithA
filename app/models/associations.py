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

# app/models/associations.py
# Association tables for many-to-many relationships

from app import db

favorite_companies = db.Table(
    "favorite_companies",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
)

competitors_association = db.Table(
    "competitors_association",
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
    db.Column(
        "competitor_id", db.Integer, db.ForeignKey("company.id"), primary_key=True
    ),
)

# Association table for linking SectorNote to Companies
sector_note_companies = db.Table(
    "sector_note_companies",
    db.Column("sector_note_id", db.Integer, db.ForeignKey("sector_note.id"), primary_key=True),
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
)

# Association table for linking SectorResearchSnippet to Companies
sector_snippet_companies = db.Table(
    "sector_snippet_companies",
    db.Column("sector_snippet_id", db.Integer, db.ForeignKey("sector_research_snippet.id"), primary_key=True),
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
)
