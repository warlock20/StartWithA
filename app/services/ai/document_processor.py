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
Document Processing Service

Handles document text extraction and conversion to checklists.

Classes:
    - DocumentParser: Extract text from PDF, DOCX, TXT files
    - LLMChecklistProcessor: Convert documents to checklists using AI
"""

import json
import logging
from app.services.ai.config import AIProvider
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.ai_check.context import ai_context_from_data
from app.utils.time_utils import now_utc
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Longest document text sent to the model; the rest is dropped.
MAX_DOCUMENT_CHARS = 60000

# ChecklistItem.text is String(500).
MAX_ITEM_TEXT_CHARS = 500

# ============================================================
# Document Parsing
# ============================================================

try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


def get_supported_file_types() -> List[str]:
    """Get list of supported file types"""
    types = ['txt']
    if PDF_SUPPORT:
        types.append('pdf')
    if DOCX_SUPPORT:
        types.extend(['docx', 'doc'])
    return types


class DocumentParser:
    """Extract text from various document formats"""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        if not PDF_SUPPORT:
            raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")
        
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text.strip()

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        if not DOCX_SUPPORT:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
        
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs).strip()

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read().strip()

    @classmethod
    def extract_text(cls, file_path: str, file_type: str) -> str:
        """Extract text based on file type"""
        file_type = file_type.lower().strip('.')
        
        if file_type == 'pdf':
            return cls.extract_text_from_pdf(file_path)
        elif file_type in ['docx', 'doc']:
            return cls.extract_text_from_docx(file_path)
        elif file_type == 'txt':
            return cls.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")


# ============================================================
# Checklist Processing
# ============================================================

class ProcessingApproach(Enum):
    IMMEDIATE = "immediate"
    INTERACTIVE = "interactive"


@dataclass
class ChecklistItem:
    text: str
    llm_prompt: Optional[str] = None
    ai_context: Optional[dict] = None
    parent_id: Optional[int] = None
    order: int = 0
    confidence: float = 1.0
    category: Optional[str] = None


@dataclass
class ProcessingResult:
    success: bool
    items: List[ChecklistItem]
    suggested_name: str
    suggested_description: str
    error_message: Optional[str] = None
    processing_time: float = 0.0
    tokens_used: int = 0


class LLMChecklistProcessor:
    """Convert documents to structured checklists using AI"""

    def __init__(self, provider: Optional[AIProvider] = None, user_id: Optional[int] = None):
        # Lazy import to avoid circular dependency
        from app.services.ai.ai_service import get_ai_service
        self.ai = get_ai_service()
        self.provider = provider
        self.user_id = user_id

    def process_document(
        self,
        document_text: str,
        approach: ProcessingApproach = ProcessingApproach.IMMEDIATE
    ) -> ProcessingResult:
        """Convert document text to checklist"""
        start_time = now_utc()

        if not self.ai.is_available():
            return ProcessingResult(
                success=False,
                items=[],
                suggested_name="",
                suggested_description="",
                error_message="AI service not available",
                processing_time=(now_utc() - start_time).total_seconds()
            )

        try:
            prompt_data = prompt_service.get_prompt_with_metadata(
                'document_processing',
                f'document_to_checklist_{approach.value}',
                document_text=document_text[:MAX_DOCUMENT_CHARS],
            )
            metadata = prompt_data.get('metadata', {})
            model, provider = resolve_model_provider(
                metadata, user_id=self.user_id, prompt_category='document_processing',
            )
            # ai_service raises when model and provider disagree, so a provider the user
            # chose that differs from the prompt's model gets its own default model.
            if self.provider and self.provider != provider:
                provider, model = self.provider, None

            response = self.ai.generate_json(
                prompt_data['prompt'],
                provider=provider, model=model,
                max_tokens=metadata.get('max_tokens'),
                temperature=metadata.get('temperature'),
            )
            items = self._parse_response(response)
            tokens_used = len(prompt_data['prompt']) // 4 + len(json.dumps(response, default=str)) // 4
            if not isinstance(response, dict):
                response = {}

            return ProcessingResult(
                success=True,
                items=items,
                suggested_name=response.get('suggested_name') or 'Imported Checklist',
                suggested_description=response.get('suggested_description') or '',
                processing_time=(now_utc() - start_time).total_seconds(),
                tokens_used=tokens_used,
            )

        except Exception:
            logger.exception("Document processing error")
            return ProcessingResult(
                success=False,
                items=[],
                suggested_name="",
                suggested_description="",
                error_message="The AI could not process this document. Please try again.",
                processing_time=(now_utc() - start_time).total_seconds()
            )

    @staticmethod
    def _build_item(data: Dict, **extra) -> Optional[ChecklistItem]:
        """ChecklistItem from one response entry, None when it has no text."""
        text = data.get('text')
        text = text.strip()[:MAX_ITEM_TEXT_CHARS] if isinstance(text, str) else ''
        if not text:
            return None
        ai_context = ai_context_from_data(data)
        llm_prompt = data.get('llm_prompt')
        if not llm_prompt and ai_context:
            # The interactive review form edits llm_prompt, so show the method there.
            llm_prompt = ai_context.get('method')
        confidence = data.get('confidence', 1.0)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            confidence = 1.0
        return ChecklistItem(text=text, llm_prompt=llm_prompt or None, ai_context=ai_context,
                             confidence=min(1.0, max(0.0, float(confidence))), **extra)

    def _parse_response(self, response: Dict) -> List[ChecklistItem]:
        """Parse AI response into ChecklistItem list"""
        items = []
        if not isinstance(response, dict) or not isinstance(response.get('items'), list):
            return items
        order = 0

        for item_data in response['items']:
            if not isinstance(item_data, dict):
                continue
            item = self._build_item(item_data, category=item_data.get('category'), order=order)
            if item is None:
                continue
            items.append(item)
            parent_idx = order
            order += 1

            subs = item_data.get('sub_items')
            for sub in subs if isinstance(subs, list) else []:
                if not isinstance(sub, dict):
                    continue
                sub_item = self._build_item(sub, parent_id=parent_idx, order=order)
                if sub_item is None:
                    continue
                items.append(sub_item)
                order += 1

        return items
