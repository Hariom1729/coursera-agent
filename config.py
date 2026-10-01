"""Configuration management for Coursera Automation Agent.

Loads settings from config.yaml and environment variables with Pydantic validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Automatically load .env if present
load_dotenv()


class CourseConfig(BaseModel):
    url: str = Field(default="", description="Coursera course home or syllabus URL")
    name: str = Field(default="", description="Course title or friendly label")


class BrowserConfig(BaseModel):
    profile_path: str = Field(default="./browser_profile", description="Persistent user data directory")
    headless: bool = Field(default=False, description="Whether to run browser headless")
    viewport_width: int = Field(default=1440, description="Browser window width")
    viewport_height: int = Field(default=900, description="Browser window height")
    slow_mo: int = Field(default=0, description="Delay between actions in milliseconds")


class AutomationConfig(BaseModel):
    auto_resume: bool = Field(default=True, description="Automatically resume from last saved state")
    retry_count: int = Field(default=5, description="Max retries for transient failures")
    retry_delay: float = Field(default=2.0, description="Base exponential retry delay in seconds")
    screenshots: bool = Field(default=True, description="Enable automatic failure and assessment screenshots")
    auto_submit_assessments: bool = Field(default=True, description="Automatically solve and submit assessments")


class GeminiConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable Google Gemini provider")
    api_key_env: str = Field(default="GEMINI_API_KEY", description="Environment variable holding Gemini API key")
    model: str = Field(default="gemini-3.8-flash", description="Gemini model name")

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


class LocalLLMConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable local OpenAI-compatible endpoint")
    base_url: str = Field(default="http://127.0.0.1:1234/v1", description="LM Studio base URL")
    model: str = Field(default="qwen3.5-4b", description="Default local model identifier")


class VerificationConfig(BaseModel):
    enabled: bool = Field(default=True, description="Verify primary answers with secondary model")
    confidence_threshold: float = Field(default=0.80, description="Threshold above which review is not forced")


class AIConfig(BaseModel):
    primary_provider: str = Field(default="gemini", description="Default primary provider: 'gemini' or 'local'")
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)


class NotificationsConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable desktop and terminal notifications")
    on_start: bool = Field(default=True)
    on_assessment: bool = Field(default=True)
    on_error: bool = Field(default=True)
    on_completion: bool = Field(default=True)
    on_certificate: bool = Field(default=True)


class DatabaseConfig(BaseModel):
    path: str = Field(default="./database/coursera.db", description="Path to SQLite database")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    file: str = Field(default="./logs/agent.log", description="Path to log file")


class AppConfig(BaseModel):
    course: CourseConfig = Field(default_factory=CourseConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    """Load configuration from YAML file and apply environment variable overrides."""
    config_dict: Dict[str, Any] = {}
    path = Path(config_path)

    if path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                config_dict = loaded

    # Allow environment variable overrides for critical parameters
    if os.environ.get("COURSERA_COURSE_URL"):
        config_dict.setdefault("course", {})["url"] = os.environ["COURSERA_COURSE_URL"]

    if os.environ.get("GEMINI_MODEL"):
        config_dict.setdefault("ai", {}).setdefault("gemini", {})["model"] = os.environ["GEMINI_MODEL"]

    if os.environ.get("LOCAL_LLM_URL"):
        config_dict.setdefault("ai", {}).setdefault("local", {})["base_url"] = os.environ["LOCAL_LLM_URL"]

    if os.environ.get("LOCAL_LLM_MODEL"):
        config_dict.setdefault("ai", {}).setdefault("local", {})["model"] = os.environ["LOCAL_LLM_MODEL"]

    return AppConfig.model_validate(config_dict)
