# Investment Checklist Platform
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
Deepseek AI Provider Implementation

"""
import os
import logging
from typing import Dict, List, Optional, Any

from .base import AIProvider
from ..config import get_ai_config, AIModel, AIProvider as AIProviderEnum

logger = logging.getLogger(__name__)

from openai import OpenAI
_deepseek_available = False
_deepseek = None

def __initialize_deepseek():
    """
    Initialize Deepseek SDK or API client.
    """
    global _deepseek_available, _deepseek
    
    if _deepseek is not None:
        return _deepseek_available
    
    try:
        import deepseek  as deepseek_sdk  # Assuming deepseek is the SDK name
        _deepseek = deepseek_sdk
        
        config = get_ai_config()
        if not config.deepseek_api_key:
            logger.warning("Deepseek API key is not configured.")
            _deepseek_available = False
            raise ValueError("Deepseek API key is not configured.")
        
        # Perform any necessary initialization here
        logger.info("Deepseek SDK initialized successfully.")
    except ImportError as e:
        logger.error("Deepseek SDK is not installed. Please install it to use this provider.")
        raise e

class DeepseekProvider(AIProvider):
    """
    Deepseek AI Provider Implementation
    """
    def __init__(self, model: Optional[AIModel] = None):
        """
        Initialize Deepseek AI Provider with configuration.
        
        Args:
            model (Optional[AIModel]): The AI model to use. If None, defaults to
        """
        self._config = get_ai_config()
        
        __initialize_deepseek()