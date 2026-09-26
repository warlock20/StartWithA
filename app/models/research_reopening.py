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

"""One record per time a rejected company was pulled back into research.

Reopening has to clear the very fields that record the rejection -- the state
ladder reads `decision`, `too_hard_reason` and `status`, so a project cannot
read as 'researching' while they still say 'pass'. Wiping them in place is what
`reactivate_project` did, and it destroyed the only record of why the company
was passed on. The snapshot lands here first, and stays.
"""

from app import db
from app.utils.time_utils import now_utc


class ResearchReopening(db.Model):
    __tablename__ = 'research_reopenings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    # ondelete='SET NULL': the snapshot outlives the rows it points at. A
    # reopened project can still be deleted (delete_research_project does not
    # clear these), and without the DB-level SET NULL that delete fails on a
    # foreign key violation -- so reopening a project made it undeletable.
    # Provenance is nice to have; the prior_* snapshot is the point, and
    # company_id (NOT NULL) is what every reader scopes by.
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id', ondelete='SET NULL'))
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id', ondelete='SET NULL'))

    # 'research' | 'pipeline' | 'sweep' -- which stage recorded the kill.
    prior_stage = db.Column(db.String(20), nullable=False)
    prior_reason = db.Column(db.Text)
    prior_notes = db.Column(db.Text)
    prior_killed_at = db.Column(db.DateTime)

    what_changed = db.Column(db.Text)
    reopened_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    company = db.relationship('Company')
    project = db.relationship('ResearchProject')
    idea = db.relationship('IdeaPipeline')

    def __repr__(self):
        return f'<ResearchReopening company={self.company_id} stage={self.prior_stage}>'
