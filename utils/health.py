"""System diagnostic tool (Doctor) verifying environment, browser, models, and database."""

from __future__ import annotations

import os
import sys
import platform
from pathlib import Path
from typing import Dict, List, Any
import httpx

from config import AppConfig
from database.database import DatabaseSessionManager


class SystemDoctor:
    """Runs end-to-end diagnostics and health checks on all subsystems."""

    def __init__(self, config: AppConfig):
        self.config = config

    async def check_all(self) -> Dict[str, Any]:
        """Run all system checks and return structured status."""
        results: Dict[str, Any] = {}

        # 1. Python Check
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        py_ok = sys.version_info >= (3, 11)
        results["python"] = {
            "ok": py_ok,
            "version": py_ver,
            "message": f"Python {py_ver}" if py_ok else f"Python {py_ver} (Requires >= 3.11)",
        }

        # 2. Playwright Check
        try:
            import playwright
            results["playwright"] = {"ok": True, "message": "Playwright installed"}
        except ImportError:
            results["playwright"] = {"ok": False, "message": "Playwright not installed"}

        # 3. Chromium Check
        chromium_path = None
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                chromium_path = p.chromium.executable_path
                results["chromium"] = {"ok": True, "path": chromium_path, "message": "Chromium available"}
        except Exception as e:
            results["chromium"] = {"ok": False, "message": f"Chromium error: {e}"}

        # 4. Browser Profile Check
        prof_dir = Path(self.config.browser.profile_path)
        prof_dir.mkdir(parents=True, exist_ok=True)
        results["browser_profile"] = {"ok": True, "path": str(prof_dir.resolve()), "message": "Browser profile ready"}

        # 5. SQLite Check
        try:
            db_mgr = DatabaseSessionManager(db_path=self.config.database.path)
            await db_mgr.create_all()
            await db_mgr.close()
            results["database"] = {"ok": True, "message": f"SQLite ready ({self.config.database.path})"}
        except Exception as e:
            results["database"] = {"ok": False, "message": f"SQLite error: {e}"}

        # 6. Gemini API Key Check
        gemini_key = self.config.ai.gemini.api_key
        has_gemini_key = bool(gemini_key and len(gemini_key) > 5)
        results["gemini_key"] = {
            "ok": has_gemini_key,
            "message": "GEMINI_API_KEY found" if has_gemini_key else "GEMINI_API_KEY missing in environment/.env",
        }

        # 7. Gemini API Connection Check
        if has_gemini_key and self.config.ai.gemini.enabled:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                res = await client.aio.models.generate_content(
                    model=self.config.ai.gemini.model,
                    contents="Ping",
                )
                results["gemini_api"] = {
                    "ok": True,
                    "model": self.config.ai.gemini.model,
                    "message": f"Gemini API connected ({self.config.ai.gemini.model})",
                }
            except Exception as e:
                results["gemini_api"] = {"ok": False, "message": f"Gemini API connection failed: {e}"}
        else:
            results["gemini_api"] = {
                "ok": False,
                "message": "Gemini API skipped (no key or disabled)",
            }

        # 8. Local LM Studio Connection Check
        local_url = self.config.ai.local.base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=4.0) as http_client:
                r = await http_client.get(f"{local_url}/models")
                if r.status_code == 200:
                    models_data = r.json().get("data", [])
                    model_ids = [m.get("id") for m in models_data if m.get("id")]
                    results["lm_studio"] = {
                        "ok": True,
                        "models": model_ids,
                        "message": f"LM Studio detected at {local_url} ({len(model_ids)} models)",
                    }
                else:
                    results["lm_studio"] = {
                        "ok": False,
                        "message": f"LM Studio returned status {r.status_code}",
                    }
        except Exception:
            results["lm_studio"] = {
                "ok": False,
                "message": f"LM Studio not reachable at {local_url} (Optional fallback)",
            }

        # 9. Course Configuration Check
        has_url = bool(self.config.course.url and "coursera.org" in self.config.course.url)
        results["course"] = {
            "ok": has_url,
            "message": f"Course URL: {self.config.course.url}" if has_url else "Course URL not configured in config.yaml",
        }

        return results

    def print_report(self, results: Dict[str, Any]):
        """Print formatted terminal report."""
        print("\n==================================")
        print(" Coursera Agent Diagnostics")
        print("==================================\n")

        for key, res in results.items():
            symbol = "✓" if res["ok"] else "✗"
            print(f"{symbol} {res['message']}")

        print("\n==================================")
        critical_ok = (
            results["python"]["ok"]
            and results["playwright"]["ok"]
            and results["chromium"]["ok"]
            and results["database"]["ok"]
        )

        if critical_ok:
            print("System core is ready.")
        else:
            print("Some critical checks failed. Please resolve above issues.")
        print("==================================\n")
