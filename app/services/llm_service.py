"""
LLM Service for Document-to-Checklist Conversion
Supports OpenAI and Google Gemini APIs
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# LLM API imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Document parsing imports
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

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class ProcessingApproach(Enum):
    IMMEDIATE = "immediate"  # Approach A: Direct processing
    INTERACTIVE = "interactive"  # Approach C: User review and editing


@dataclass
class ChecklistItem:
    """Structured checklist item from LLM processing"""
    text: str
    llm_prompt: Optional[str] = None
    parent_id: Optional[int] = None
    order: int = 0
    confidence: float = 1.0
    category: Optional[str] = None


@dataclass
class ProcessingResult:
    """Result of document processing"""
    success: bool
    items: List[ChecklistItem]
    suggested_name: str
    suggested_description: str
    error_message: Optional[str] = None
    processing_time: float = 0.0


class DocumentParser:
    """Handle document text extraction"""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from PDF file using PyMuPDF"""
        if not PDF_SUPPORT:
            raise ImportError("PyMuPDF not installed. Install with: pip install PyMuPDF")

        text = ""
        try:
            # Open PDF document
            doc = fitz.open(file_path)

            # Extract text from each page
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text() + "\n"

            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise

        return text.strip()

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Extract text from Word document"""
        if not DOCX_SUPPORT:
            raise ImportError("python-docx not installed. Install with: pip install python-docx")

        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            raise

        return text.strip()

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Extract text from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read().strip()

    @classmethod
    def extract_text(cls, file_path: str, file_type: str) -> str:
        """Extract text based on file type"""
        file_type = file_type.lower()

        if file_type == 'pdf':
            return cls.extract_text_from_pdf(file_path)
        elif file_type in ['docx', 'doc']:
            return cls.extract_text_from_docx(file_path)
        elif file_type == 'txt':
            return cls.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")


class UnifiedLLMService:
    """Unified LLM service for all AI operations across the platform"""

    def __init__(self, provider: LLMProvider = LLMProvider.GEMINI):
        self.provider = provider
        self._setup_api()

    @classmethod
    def get_instance(cls, provider: LLMProvider = LLMProvider.GEMINI):
        """Get singleton instance of LLM service"""
        if not hasattr(cls, '_instance'):
            cls._instance = cls(provider)
        return cls._instance

    def _setup_api(self):
        """Initialize API clients"""
        if self.provider == LLMProvider.OPENAI:
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI not installed. Install with: pip install openai")

            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            openai.api_key = api_key

        elif self.provider == LLMProvider.GEMINI:
            if not GEMINI_AVAILABLE:
                raise ImportError("Google Generative AI not installed. Install with: pip install google-generativeai")

            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")

            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    async def generate_content_async(self, prompt: str, **kwargs) -> str:
        """Generate content using the configured LLM provider (async)"""
        if self.provider == LLMProvider.OPENAI:
            return await self._openai_generate(prompt, **kwargs)
        else:  # GEMINI
            return self._gemini_generate(prompt, **kwargs)

    def generate_content(self, prompt: str, **kwargs) -> str:
        """Generate content using the configured LLM provider (sync)"""
        if self.provider == LLMProvider.GEMINI:
            return self._gemini_generate(prompt, **kwargs)
        else:
            raise NotImplementedError("Synchronous OpenAI calls not supported. Use generate_content_async instead.")

    def _gemini_generate(self, prompt: str, **kwargs) -> str:
        """Generate content using Gemini"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

    async def _openai_generate(self, prompt: str, **kwargs) -> str:
        """Generate content using OpenAI"""
        try:
            system_message = kwargs.get('system_message', "You are a helpful assistant.")
            max_tokens = kwargs.get('max_tokens', 2000)
            temperature = kwargs.get('temperature', 0.7)

            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    def generate_json(self, prompt: str, **kwargs) -> Dict:
        """Generate structured JSON response"""
        system_message = kwargs.get('system_message', "You are a helpful assistant. Always respond with valid JSON.")

        if self.provider == LLMProvider.GEMINI:
            try:
                response = self.model.generate_content(prompt)
                content = response.text

                # Remove markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    # Handle generic code blocks
                    parts = content.split("```")
                    if len(parts) >= 3:
                        content = parts[1].strip()

                # Try to find JSON in the response
                content = content.strip()

                # Look for JSON object boundaries
                start_idx = content.find('{')
                if start_idx == -1:
                    raise ValueError("No opening brace found in Gemini response")

                # Find matching closing brace
                brace_count = 0
                end_idx = -1
                for i, char in enumerate(content[start_idx:], start_idx):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break

                if end_idx == -1:
                    raise ValueError("No matching closing brace found in Gemini response")

                json_content = content[start_idx:end_idx]
                return json.loads(json_content)

            except json.JSONDecodeError as e:
                logger.error(f"Gemini JSON generation error: {e}")
                logger.error(f"Content that failed to parse: {content}")
                raise ValueError(f"No valid JSON found in response: {str(e)}")
            except Exception as e:
                logger.error(f"Gemini JSON generation error: {e}")
                raise
        else:
            raise NotImplementedError("OpenAI JSON generation not implemented yet")


class LLMChecklistProcessor(UnifiedLLMService):
    """Specialized service for document-to-checklist conversion"""

    def __init__(self, provider: LLMProvider = LLMProvider.GEMINI):
        super().__init__(provider)

    def _create_prompt(self, document_text: str, approach: ProcessingApproach) -> str:
        """Create LLM prompt based on processing approach"""

        base_prompt = """
You are an expert investment analyst helping to convert a document into a structured investment checklist.

Analyze the following document and extract actionable checklist items for investment analysis.

REQUIREMENTS:
1. Extract items as hierarchical bullet points (main items and sub-items)
2. Focus on actionable analysis questions and evaluation criteria
3. Suggest relevant LLM prompts for each item where appropriate
4. Categorize items by investment analysis area when possible
5. Provide a suggested checklist name and description

DOCUMENT CONTENT:
{document_text}

IMPORTANT: Respond with ONLY valid JSON. Do not include any explanatory text, markdown formatting, or code blocks.

OUTPUT FORMAT - Return exactly this JSON structure:
{{
    "suggested_name": "Brief descriptive name for this checklist",
    "suggested_description": "2-3 sentence description of the checklist purpose",
    "items": [
        {{
            "text": "Main checklist item text",
            "llm_prompt": "Optional: Suggested LLM prompt for this item",
            "category": "Optional: Category like 'Financial', 'Competitive', 'Management', etc.",
            "sub_items": [
                {{
                    "text": "Sub-item text",
                    "llm_prompt": "Optional LLM prompt"
                }}
            ]
        }}
    ]
}}
"""

        if approach == ProcessingApproach.IMMEDIATE:
            return base_prompt + """
PROCESSING MODE: IMMEDIATE
- Provide a complete, ready-to-use checklist
- Use high confidence thresholds
- Focus on the most important items only
"""
        else:  # INTERACTIVE
            return base_prompt + """
PROCESSING MODE: INTERACTIVE
- Extract ALL potential checklist items (even uncertain ones)
- Include confidence scores for each item
- Provide multiple options where applicable
- The user will review and edit these suggestions
"""

    async def process_with_openai(self, prompt: str) -> Dict:
        """Process document using OpenAI API"""
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert investment analyst and checklist creator. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=3000,
                temperature=0.3
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def process_with_gemini(self, prompt: str) -> Dict:
        """Process document using Gemini API"""
        try:
            response = self.model.generate_content(prompt)
            content = response.text

            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Handle generic code blocks
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()

            # Try to find JSON in the response
            content = content.strip()

            # Look for JSON object boundaries
            start_idx = content.find('{')
            if start_idx == -1:
                raise ValueError("No opening brace found in Gemini response")

            # Find matching closing brace
            brace_count = 0
            end_idx = -1
            for i, char in enumerate(content[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

            if end_idx == -1:
                raise ValueError("No matching closing brace found in Gemini response")

            json_content = content[start_idx:end_idx]

            # Log the extracted JSON for debugging
            logger.debug(f"Extracted JSON: {json_content[:200]}...")

            return json.loads(json_content)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Content that failed to parse: {content}")
            raise ValueError(f"No valid JSON found in Gemini response: {str(e)}")
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def _parse_llm_response(self, response_data: Dict) -> List[ChecklistItem]:
        """Parse LLM response into ChecklistItem objects"""
        items = []
        order = 0

        for item_data in response_data.get('items', []):
            # Main item
            main_item = ChecklistItem(
                text=item_data['text'],
                llm_prompt=item_data.get('llm_prompt'),
                category=item_data.get('category'),
                confidence=item_data.get('confidence', 1.0),
                order=order
            )
            items.append(main_item)
            order += 1

            # Sub-items
            for sub_item_data in item_data.get('sub_items', []):
                sub_item = ChecklistItem(
                    text=sub_item_data['text'],
                    llm_prompt=sub_item_data.get('llm_prompt'),
                    confidence=sub_item_data.get('confidence', 1.0),
                    parent_id=len(items) - 1,  # Reference to parent item
                    order=order
                )
                items.append(sub_item)
                order += 1

        return items

    async def process_document(
        self,
        document_text: str,
        approach: ProcessingApproach
    ) -> ProcessingResult:
        """Main processing method"""
        import time
        start_time = time.time()

        try:
            prompt = self._create_prompt(document_text, approach)

            if self.provider == LLMProvider.OPENAI:
                response_data = await self.process_with_openai(prompt)
            else:  # GEMINI
                response_data = self.process_with_gemini(prompt)

            items = self._parse_llm_response(response_data)

            processing_time = time.time() - start_time

            return ProcessingResult(
                success=True,
                items=items,
                suggested_name=response_data.get('suggested_name', 'Imported Checklist'),
                suggested_description=response_data.get('suggested_description', 'Checklist imported from document'),
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return ProcessingResult(
                success=False,
                items=[],
                suggested_name="",
                suggested_description="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )


# Convenience functions
def get_available_providers() -> List[LLMProvider]:
    """Get list of available LLM providers"""
    providers = []

    if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
        providers.append(LLMProvider.OPENAI)

    if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
        providers.append(LLMProvider.GEMINI)

    return providers


def get_supported_file_types() -> List[str]:
    """Get list of supported file types"""
    types = ['txt']

    if PDF_SUPPORT:
        types.append('pdf')

    if DOCX_SUPPORT:
        types.extend(['docx', 'doc'])

    return types


# Convenience functions for easy access throughout the application
def get_llm_service(provider: LLMProvider = LLMProvider.GEMINI) -> UnifiedLLMService:
    """Get the unified LLM service instance"""
    return UnifiedLLMService.get_instance(provider)


def generate_ai_content(prompt: str, provider: LLMProvider = LLMProvider.GEMINI, **kwargs) -> str:
    """Generate AI content using the unified service"""
    service = get_llm_service(provider)
    return service.generate_content(prompt, **kwargs)


async def generate_ai_content_async(prompt: str, provider: LLMProvider = LLMProvider.GEMINI, **kwargs) -> str:
    """Generate AI content asynchronously using the unified service"""
    service = get_llm_service(provider)
    return await service.generate_content_async(prompt, **kwargs)


def generate_ai_json(prompt: str, provider: LLMProvider = LLMProvider.GEMINI, **kwargs) -> Dict:
    """Generate structured JSON response using the unified service"""
    service = get_llm_service(provider)
    return service.generate_json(prompt, **kwargs)