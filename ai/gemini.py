"""Google Gemini AI Provider implementation using modern google-genai SDK."""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_exception

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def is_transient_gemini_error(exception: BaseException) -> bool:
    """Do not retry if quota is exhausted so router can instantly fallback to local LLM."""
    err_msg = str(exception).lower()
    if "quota" in err_msg or "resource_exhausted" in err_msg or "429" in err_msg:
        return False
    return True


class GeminiProvider:
    """Provider for Google Gemini API via official google-genai SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured or provided.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception(is_transient_gemini_error),
    )
    async def analyze(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Call Gemini model with structured output support."""
        client = self._get_client()
        from google.genai import types

        config_params: Dict[str, Any] = {}
        if system_instruction:
            config_params["system_instruction"] = system_instruction

        if schema is not None:
            config_params["response_mime_type"] = "application/json"
            config_params["response_schema"] = schema

        config = types.GenerateContentConfig(**config_params) if config_params else None

        logger.debug(f"Sending prompt to Gemini model: {self.model_name}")
        # Note: genai client.aio provides async operations
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        response_text = response.text or "{}"
        if schema is not None:
            try:
                # If schema provided, parse into Pydantic model
                data = json.loads(response_text)
                return schema.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to parse structured JSON from Gemini: {e}. Raw text: {response_text[:200]}")
                # Fallback attempt
                return response_text

        return response_text

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception(is_transient_gemini_error),
    )
    async def analyze_image(
        self,
        prompt: str,
        image_path: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Analyze an image or screenshot using Gemini Vision."""
        client = self._get_client()
        from google.genai import types

        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Screenshot file not found: {image_path}")

        image_bytes = path.read_bytes()
        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        config_params: Dict[str, Any] = {}
        if system_instruction:
            config_params["system_instruction"] = system_instruction
        if schema is not None:
            config_params["response_mime_type"] = "application/json"
            config_params["response_schema"] = schema

        config = types.GenerateContentConfig(**config_params) if config_params else None

        contents = [image_part, prompt]

        logger.debug(f"Sending image ({image_path}) to Gemini model: {self.model_name}")
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        response_text = response.text or "{}"
        if schema is not None:
            try:
                data = json.loads(response_text)
                return schema.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to parse structured JSON from Gemini image response: {e}")
                return response_text

        return response_text

    async def health_check(self) -> Dict[str, Any]:
        """Verify API key and connectivity with lightweight request."""
        if not self.api_key:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY environment variable is not set.",
                "available": False,
            }

        try:
            client = self._get_client()
            res = await client.aio.models.generate_content(
                model=self.model_name,
                contents="Ping. Reply with PONG.",
            )
            return {
                "status": "ok",
                "model": self.model_name,
                "response": (res.text or "").strip()[:50],
                "available": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "available": False,
            }
