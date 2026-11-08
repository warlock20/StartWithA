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
Document Import Celery Task

Turns the text of an uploaded document into checklist items with the LLM. The
DocumentImport row is the task record: the result page reloads while it is
`processing` and shows the items or the error once it is `completed` or `failed`.
"""

import logging
from contextlib import nullcontext

from flask import has_app_context

from app import create_app, db
from app.models import DocumentImport, User
from app.services.ai.config import AIProvider
from app.services.ai.document_processor import (
    MAX_DOCUMENT_CHARS,
    LLMChecklistProcessor,
    ProcessingApproach,
)
from app.utils.time_utils import now_utc
from celery_app import celery

logger = logging.getLogger(__name__)

NO_ITEMS_MESSAGE = "No checklist items could be extracted from this document."
GENERIC_FAILURE = "Processing failed. Please try again."


# Room for the model's answer in the pre-flight estimate.
OUTPUT_TOKEN_ALLOWANCE = 3000


def estimate_tokens(raw_text):
    """Token estimate for one import: the truncated document plus room for the answer."""
    return len((raw_text or '')[:MAX_DOCUMENT_CHARS]) // 4 + OUTPUT_TOKEN_ALLOWANCE


def provider_from_value(value):
    """The AIProvider for a stored llm_provider; unknown or stale values mean no explicit provider."""
    try:
        return AIProvider(value)
    except ValueError:
        return None


def _fail(document_import, message):
    document_import.status = 'failed'
    document_import.error_message = message
    document_import.completed_at = now_utc()
    db.session.commit()


@celery.task(bind=True, name='app.celery_tasks.tasks_documents.process_document_import')
def process_document_import(self, import_id):
    """Run the LLM over a DocumentImport's raw_text and store the items on the row."""
    with nullcontext() if has_app_context() else create_app().app_context():
        document_import = db.session.get(DocumentImport, import_id)
        if not document_import:
            logger.error(f"TASK {self.request.id}: DocumentImport {import_id} not found")
            return {'status': 'failed', 'message': 'Import not found'}

        try:
            processor = LLMChecklistProcessor(
                provider_from_value(document_import.llm_provider),
                user_id=document_import.user_id,
            )
            result = processor.process_document(
                document_import.raw_text,
                ProcessingApproach(document_import.processing_approach),
            )
            document_import.processing_time = result.processing_time

            if not result.success:
                _fail(document_import, result.error_message or GENERIC_FAILURE)
                return {'status': 'failed'}
            if not result.items:
                _fail(document_import, NO_ITEMS_MESSAGE)
                return {'status': 'failed'}

            document_import.processed_items = [
                {
                    'text': item.text,
                    'llm_prompt': item.llm_prompt,
                    'ai_context': item.ai_context,
                    'category': item.category,
                    'confidence': item.confidence,
                    'parent_id': item.parent_id,
                    'order': item.order,
                }
                for item in result.items
            ]
            document_import.suggested_name = result.suggested_name
            document_import.suggested_description = result.suggested_description
            document_import.status = 'completed'
            document_import.completed_at = now_utc()

            user = db.session.get(User, document_import.user_id)
            if user:
                user.increment_ai_tokens(result.tokens_used)
            db.session.commit()
            return {'status': 'completed'}

        except Exception:
            db.session.rollback()
            logger.exception(f"TASK {self.request.id}: document import {import_id} failed")
            _fail(db.session.get(DocumentImport, import_id), GENERIC_FAILURE)
            return {'status': 'failed'}
