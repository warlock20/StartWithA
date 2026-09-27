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

"""AI check runs: one row per run, with the sources it read and the figures it extracted."""

from app import db
from app.utils.time_utils import now_utc


class AICheckRun(db.Model):
    __tablename__ = 'ai_check_run'

    MODES = ('documents', 'web', 'both')
    TERMINAL_STATUSES = ('completed', 'failed', 'cancelled')

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id', ondelete='CASCADE'),
                                  nullable=False, index=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('checklist_analysis.id', ondelete='SET NULL'),
                            nullable=True)
    mode = db.Column(db.String(20), nullable=False)
    document_ids = db.Column(db.JSON, nullable=False, default=list)
    # The question text + ai_context as they were when the run started.
    context_snapshot = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='queued', index=True)
    failed_stage = db.Column(db.String(20), nullable=True)
    error = db.Column(db.Text, nullable=True)
    result = db.Column(db.JSON, nullable=True)
    models = db.Column(db.JSON, nullable=False, default=dict)
    tokens_in = db.Column(db.Integer, nullable=False, default=0)
    tokens_out = db.Column(db.Integer, nullable=False, default=0)
    cache_read_tokens = db.Column(db.Integer, nullable=False, default=0)
    web_searches = db.Column(db.Integer, nullable=False, default=0)
    web_fetches = db.Column(db.Integer, nullable=False, default=0)
    cost_estimate = db.Column(db.Float, nullable=False, default=0.0)
    loop_back_used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    sources = db.relationship('AICheckSource', backref='run', cascade='all, delete-orphan',
                              order_by='AICheckSource.id')
    evidence = db.relationship('AICheckEvidence', backref='run', cascade='all, delete-orphan',
                               order_by='AICheckEvidence.id')

    __table_args__ = (
        db.Index('ix_ai_check_run_user_company_item', 'user_id', 'company_id', 'checklist_item_id'),
    )

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES


class AICheckSource(db.Model):
    __tablename__ = 'ai_check_source'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('ai_check_run.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)  # document | web
    company_resource_id = db.Column(db.Integer,
                                    db.ForeignKey('company_resource.id', ondelete='SET NULL'),
                                    nullable=True)
    url = db.Column(db.String(1000), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    doc_type = db.Column(db.String(100), nullable=True)
    period = db.Column(db.String(50), nullable=True)
    gap_filled = db.Column(db.Text, nullable=True)
    extract_status = db.Column(db.String(20), nullable=False, default='queued')
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    evidence = db.relationship('AICheckEvidence', backref='source', order_by='AICheckEvidence.id')


class AICheckEvidence(db.Model):
    __tablename__ = 'ai_check_evidence'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('ai_check_run.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('ai_check_source.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    label = db.Column(db.String(10), nullable=True)  # E1, E2 … assigned at Analyze
    metric = db.Column(db.String(300), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    value_numeric = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    period = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(300), nullable=True)
    quote = db.Column(db.Text, nullable=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)
