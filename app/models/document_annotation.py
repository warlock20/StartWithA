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

"""Document Annotation model for pinning notes to PDF pages."""

from app import db
from app.utils.time_utils import now_utc


class DocumentAnnotation(db.Model):
    """An annotation on a document page — either a point-pin or a text highlight.

    For point-pins: x_percent/y_percent store the pin position.
    For text highlights: anchor_text stores the selected text, x_percent/y_percent
    are nullable (position derived from the text layer at render time).
    """

    __tablename__ = 'document_annotation'

    ANNOTATION_TYPE_PIN = 'pin'
    ANNOTATION_TYPE_HIGHLIGHT = 'highlight'

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(
        db.Integer,
        db.ForeignKey('company_resource.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('company.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    annotation_type = db.Column(db.String(20), default='pin', nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    x_percent = db.Column(db.Float, nullable=True)
    y_percent = db.Column(db.Float, nullable=True)
    anchor_text = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=False)
    scope = db.Column(db.String(20), default='company', nullable=False)

    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    # Relationships
    resource = db.relationship(
        'CompanyResource',
        backref=db.backref('annotations', lazy='dynamic', cascade='all, delete-orphan'),
    )
    company = db.relationship(
        'Company',
        backref=db.backref('annotations', lazy='dynamic'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'resource_id': self.resource_id,
            'company_id': self.company_id,
            'annotation_type': self.annotation_type,
            'page_number': self.page_number,
            'x_percent': self.x_percent,
            'y_percent': self.y_percent,
            'anchor_text': self.anchor_text,
            'content': self.content,
            'scope': self.scope,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<DocumentAnnotation {self.id} on Resource {self.resource_id} p{self.page_number}>'
