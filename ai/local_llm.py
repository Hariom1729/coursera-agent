"""Local LLM Provider for LM Studio via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LocalLLMClient:
    """Client for local OpenAI-compatible LLM servers (LM Studio, Ollama, vLLM)."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        default_model: str = "qwen3.5-4b",
        timeout: float = 35.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="lm-studio",  # LM Studio does not require a real key, but OpenAI SDK expects one
            timeout=self.timeout,
        )

    async def list_models(self) -> List[str]:
        """Fetch available models from /v1/models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.get(f"{self.base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models_data = data.get("data", [])
                    return [m.get("id", "") for m in models_data if m.get("id")]
                return []
        except Exception as e:
            logger.debug(f"Could not connect to LM Studio at {self.base_url}: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check if local endpoint is reachable and return active models."""
        models = await self.list_models()
        if models:
            return {
                "status": "ok",
                "available": True,
                "base_url": self.base_url,
                "models": models,
                "selected_model": self.default_model if self.default_model in models else models[0],
            }
        return {
            "status": "unavailable",
            "available": False,
            "base_url": self.base_url,
            "message": f"No models found or connection refused at {self.base_url}",
        }

    async def _resolve_model(self) -> str:
        """Resolve model name, falling back to first detected model if configured one is absent."""
        available = await self.list_models()
        if not available:
            return self.default_model
        if self.default_model in available:
            return self.default_model
        # Use first available model
        logger.warning(
            f"Configured local model '{self.default_model}' not found in LM Studio. Using '{available[0]}'."
        )
        return available[0]

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=1, max=10),
    )
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate unstructured text from local LLM."""
        chosen_model = model or await self._resolve_model()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        return content

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1.0, min=0.5, max=2.0),
    )
    async def analyze(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Analyze text and parse into structured schema."""
        chosen_model = model or await self._resolve_model()

        # Optimize input length for local inference performance
        trimmed_prompt = prompt[:1500] if len(prompt) > 1500 else prompt

        # If schema is given, instruct model to output strictly valid JSON
        structured_system = system_instruction or "You are an educational reasoning assistant."
        if schema is not None:
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            structured_system += f"\n\nCRITICAL: Respond ONLY with a valid JSON object strictly matching this JSON schema:\n{schema_json}\nDo not include code fences or extra text."

        raw_output = await self.generate(
            prompt=trimmed_prompt,
            system_instruction=structured_system,
            model=chosen_model,
            temperature=0.1,
        )

        if schema is not None:
            # Strip potential markdown fences
            cleaned = raw_output.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            try:
                data = json.loads(cleaned)
                return schema.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to parse structured JSON from local model: {e}. Output was: {cleaned[:200]}")
                return raw_output

        return raw_output

    async def analyze_image(
        self,
        prompt: str,
        image_path: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Fallback for image analysis on local model (describes inability if vision not supported)."""
        logger.warning("Local LM Studio model does not have direct vision capabilities enabled; falling back to prompt context.")
        text_prompt = f"[Note: An image exists at {image_path} with diagram details.]\n{prompt}"
        return await self.analyze(text_prompt, system_instruction=system_instruction, schema=schema, **kwargs)
