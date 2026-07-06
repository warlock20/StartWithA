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

import logging
from app.utils.time_utils import now_utc
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

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


class LLMChecklistProcessor:
    """Convert documents to structured checklists using AI"""

    def __init__(self):
        # Lazy import to avoid circular dependency
        from app.services.ai.ai_service import get_ai_service
        self.ai = get_ai_service()

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
                processing_time=now_utc() - start_time
            )

        try:
            prompt = self._create_prompt(document_text, approach)
            response = self.ai.generate_json(prompt)
            items = self._parse_response(response)

            return ProcessingResult(
                success=True,
                items=items,
                suggested_name=response.get('suggested_name', 'Imported Checklist'),
                suggested_description=response.get('suggested_description', ''),
                processing_time=now_utc() - start_time
            )

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return ProcessingResult(
                success=False,
                items=[],
                suggested_name="",
                suggested_description="",
                error_message=str(e),
                processing_time=now_utc() - start_time
            )

    def _create_prompt(self, document_text: str, approach: ProcessingApproach) -> str:
        """Create prompt for document conversion"""
        try:
            from app.services.ai.prompt_service import get_document_processing_prompt
            prompt_name = f'document_to_checklist_{approach.value}'
            return get_document_processing_prompt(prompt_name, document_text=document_text)
        except Exception:
            # Fallback prompt if YAML not found
            return f"""Convert this document into an investment research checklist.

DOCUMENT:
{document_text[:8000]}

Return JSON with:
- suggested_name: Checklist name
- suggested_description: Brief description  
- items: Array of objects with: text, llm_prompt (optional), category, confidence (0-1), sub_items (optional array)"""

    def _parse_response(self, response: Dict) -> List[ChecklistItem]:
        """Parse AI response into ChecklistItem list"""
        items = []
        order = 0

        for item_data in response.get('items', []):
            items.append(ChecklistItem(
                text=item_data.get('text', ''),
                llm_prompt=item_data.get('llm_prompt'),
                confidence=item_data.get('confidence', 1.0),
                category=item_data.get('category'),
                order=order
            ))
            parent_idx = order
            order += 1

            for sub in item_data.get('sub_items', []):
                items.append(ChecklistItem(
                    text=sub.get('text', ''),
                    llm_prompt=sub.get('llm_prompt'),
                    confidence=sub.get('confidence', 1.0),
                    parent_id=parent_idx,
                    order=order
                ))
                order += 1

        return items
