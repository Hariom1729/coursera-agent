"""AI Router coordinating Gemini, Local LLM, Verification, and Caching."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.base import AIProvider
from ai.gemini import GeminiProvider
from ai.local_llm import LocalLLMClient
from ai.verifier import AIVerifier
from ai.schemas import (
    QuestionAnalysis,
    ModelComparisonResult,
    ModelOpinion,
)
from ai.cache import AICache
from config import AIConfig

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AIRouter(AIProvider):
    """Central router managing LLM queries, cross-model verification, and failovers."""

    def __init__(
        self,
        config: AIConfig,
        cache: Optional[AICache] = None,
    ):
        self.config = config
        self.cache = cache
        self._gemini_cooldown_until: float = 0.0
        self.verifier = AIVerifier(
            confidence_threshold=config.verification.confidence_threshold
        )

        self.gemini = (
            GeminiProvider(
                api_key=config.gemini.api_key,
                model_name=config.gemini.model,
            )
            if config.gemini.enabled
            else None
        )

        self.local = (
            LocalLLMClient(
                base_url=config.local.base_url,
                default_model=config.local.model,
            )
            if config.local.enabled
            else None
        )

    async def health_check(self) -> Dict[str, Any]:
        """Check status of all configured providers."""
        results: Dict[str, Any] = {"providers": {}}

        if self.gemini:
            results["providers"]["gemini"] = await self.gemini.health_check()
        else:
            results["providers"]["gemini"] = {"status": "disabled", "available": False}

        if self.local:
            results["providers"]["local"] = await self.local.health_check()
        else:
            results["providers"]["local"] = {"status": "disabled", "available": False}

        results["primary"] = self.config.primary_provider
        results["verification_enabled"] = self.config.verification.enabled
        return results

    async def analyze(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Analyze text with primary model, falling back to secondary if primary fails."""
        model_name = self.config.gemini.model if self.config.primary_provider == "gemini" else self.config.local.model

        # 1. Check Cache
        if use_cache and self.cache:
            cached = await self.cache.get(prompt, model=model_name, schema=schema)
            if cached is not None:
                return cached

        is_gemini_primary = (self.config.primary_provider == "gemini")
        if is_gemini_primary and time.time() < self._gemini_cooldown_until:
            logger.info("Gemini in cooldown (quota/rate-limit). Routing directly to local model...")
            primary = None
            secondary = self.local
        else:
            primary = self.gemini if is_gemini_primary else self.local
            secondary = self.local if is_gemini_primary else self.gemini

        # 2. Try Primary
        if primary:
            try:
                result = await primary.analyze(prompt, system_instruction=system_instruction, schema=schema, **kwargs)
                if use_cache and self.cache:
                    cand_ans = getattr(result, "candidate_answer", None) or getattr(result, "answer", None)
                    conf = getattr(result, "confidence", 0.0)
                    await self.cache.put(
                        content=prompt,
                        provider=self.config.primary_provider,
                        model=model_name,
                        response_data=result,
                        candidate_answer=cand_ans,
                        confidence=conf,
                    )
                return result
            except Exception as e:
                err_str = str(e).lower()
                if is_gemini_primary and ("429" in err_str or "quota" in err_str or "503" in err_str or "unavailable" in err_str):
                    logger.warning("Gemini rate limit or high demand detected. Entering 60s cooldown.")
                    self._gemini_cooldown_until = time.time() + 60.0
                logger.warning(f"Primary AI provider ({self.config.primary_provider}) failed: {e}. Attempting fallback...")

        # 3. Try Secondary/Fallback
        if secondary:
            try:
                fallback_model = self.config.local.model if self.config.primary_provider == "gemini" else self.config.gemini.model
                logger.info("Engaging secondary AI provider fallback...")
                result = await secondary.analyze(prompt, system_instruction=system_instruction, schema=schema, **kwargs)
                if use_cache and self.cache:
                    cand_ans = getattr(result, "candidate_answer", None) or getattr(result, "answer", None)
                    conf = getattr(result, "confidence", 0.0)
                    await self.cache.put(
                        content=prompt,
                        provider="fallback",
                        model=fallback_model,
                        response_data=result,
                        candidate_answer=cand_ans,
                        confidence=conf,
                    )
                return result
            except Exception as e:
                logger.error(f"Secondary AI provider also failed: {e}")

        raise RuntimeError("All configured AI providers failed or are unavailable.")

    async def analyze_image(
        self,
        prompt: str,
        image_path: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Any:
        """Analyze an image using Gemini Vision, falling back to text description with local model."""
        if self.gemini:
            try:
                return await self.gemini.analyze_image(
                    prompt=prompt,
                    image_path=image_path,
                    system_instruction=system_instruction,
                    schema=schema,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(f"Gemini Vision failed: {e}. Falling back to secondary...")

        if self.local:
            return await self.local.analyze_image(
                prompt=prompt,
                image_path=image_path,
                system_instruction=system_instruction,
                schema=schema,
                **kwargs,
            )

        raise RuntimeError("No AI provider available for image analysis.")

    async def analyze_and_verify_question(
        self,
        question_prompt: str,
        screenshot_path: Optional[str] = None,
    ) -> tuple[QuestionAnalysis, ModelComparisonResult]:
        """Analyze assessment question with both models and cross-verify answers."""
        gemini_analysis: Optional[QuestionAnalysis] = None
        local_analysis: Optional[QuestionAnalysis] = None

        # 1. Query Gemini
        if self.gemini:
            try:
                if screenshot_path:
                    gemini_analysis = await self.gemini.analyze_image(
                        prompt=question_prompt,
                        image_path=screenshot_path,
                        schema=QuestionAnalysis,
                    )
                else:
                    gemini_analysis = await self.gemini.analyze(
                        prompt=question_prompt,
                        schema=QuestionAnalysis,
                    )
            except Exception as e:
                logger.warning(f"Gemini failed during question analysis: {e}")

        # 2. Query Local LLM if verification enabled or Gemini failed
        if self.local and (self.config.verification.enabled or not gemini_analysis):
            try:
                local_analysis = await self.local.analyze(
                    prompt=question_prompt,
                    schema=QuestionAnalysis,
                )
            except Exception as e:
                logger.warning(f"Local LLM failed during question analysis/verification: {e}")

        # 3. Cross-verify
        comparison = self.verifier.verify(gemini_analysis, local_analysis)

        # Primary question analysis to return
        primary_analysis = gemini_analysis or local_analysis
        if primary_analysis is None:
            raise RuntimeError("Failed to obtain question analysis from any AI provider.")

        # Update primary analysis with verification consensus
        primary_analysis.requires_review = comparison.requires_review
        if comparison.consensus_answer:
            primary_analysis.candidate_answer = comparison.consensus_answer
        primary_analysis.confidence = comparison.final_confidence

        return primary_analysis, comparison
