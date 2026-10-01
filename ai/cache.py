"""Content-hash based response caching to prevent duplicate AI calls and control costs."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel

from database.database import DatabaseSessionManager
from database.repositories import AICacheRepository

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AICache:
    """Computes deterministic hashes of content and caches AI analysis in SQLite."""

    def __init__(self, db_manager: DatabaseSessionManager):
        self.db_manager = db_manager

    @staticmethod
    def compute_hash(content: str, prompt_version: str = "v1") -> str:
        """Compute SHA256 of normalized text content and prompt version."""
        normalized = " ".join(content.strip().split())
        payload = f"{prompt_version}:{normalized}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def get(
        self,
        content: str,
        model: str,
        schema: Optional[Type[T]] = None,
        prompt_version: str = "v1",
    ) -> Optional[Any]:
        """Retrieve cached result if exists."""
        content_hash = self.compute_hash(content, prompt_version)
        try:
            async with self.db_manager.session() as session:
                repo = AICacheRepository(session)
                cached = await repo.get_cached_analysis(content_hash, model)
                if cached:
                    logger.debug(f"Cache hit for hash {content_hash[:8]} (model: {model})")
                    if schema is not None:
                        data = json.loads(cached.response_json)
                        return schema.model_validate(data)
                    return cached.response_json
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        return None

    async def put(
        self,
        content: str,
        provider: str,
        model: str,
        response_data: Any,
        candidate_answer: Optional[str] = None,
        confidence: float = 0.0,
        agreement: Optional[bool] = None,
        requires_review: bool = False,
        question_id: Optional[str] = None,
        prompt_version: str = "v1",
    ):
        """Save AI analysis into cache table."""
        content_hash = self.compute_hash(content, prompt_version)
        if isinstance(response_data, BaseModel):
            response_json = response_data.model_dump_json()
        elif isinstance(response_data, (dict, list)):
            response_json = json.dumps(response_data)
        else:
            response_json = str(response_data)

        try:
            async with self.db_manager.session() as session:
                repo = AICacheRepository(session)
                await repo.save_analysis(
                    content_hash=content_hash,
                    provider=provider,
                    model=model,
                    response_json=response_json,
                    candidate_answer=candidate_answer,
                    confidence=confidence,
                    agreement=agreement,
                    requires_review=requires_review,
                    question_id=question_id,
                    prompt_version=prompt_version,
                )
                logger.debug(f"Saved analysis to cache for hash {content_hash[:8]}")
        except Exception as e:
            logger.warning(f"Failed to persist cache entry: {e}")
