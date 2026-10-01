"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    """Abstract interface for LLM providers (Gemini, Local LM Studio, etc.)."""

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Analyze text input and return structured object or dictionary."""
        pass

    @abstractmethod
    async def analyze_image(
        self,
        prompt: str,
        image_path: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Analyze an image or screenshot along with textual prompt."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform provider health check and connectivity test."""
        pass
