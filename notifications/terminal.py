"""Terminal UI formatter and status display."""

from __future__ import annotations

import sys
from typing import Optional


class TerminalNotifier:
    """Renders formatted console banners, lesson cards, and progress bars."""

    @staticmethod
    def render_startup_banner(ai_provider: str, local_model: str, browser: str = "Playwright Chromium"):
        banner = f"""
╔══════════════════════════════════════════════════════════════════╗
║                   COURSERA AI COURSE AGENT                       ║
╚══════════════════════════════════════════════════════════════════╝

Primary AI Provider : {ai_provider.upper()}
Local Fallback/Eval : {local_model}
Browser Automation  : {browser}
State Store         : SQLite (Async)

Checking system dependencies...
"""
        print(banner)

    @staticmethod
    def render_lesson_card(
        module_num: int,
        total_modules: int,
        lesson_title: str,
        lesson_type: str,
        progress_pct: float,
        ai_status: str = "Ready",
    ):
        bar_length = 20
        filled_length = int(bar_length * (progress_pct / 100.0))
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        card = f"""
------------------------------------------------------------------
[MODULE {module_num}/{total_modules}]

Lesson   : {lesson_title[:50]}
Type     : {lesson_type.capitalize()}
AI State : {ai_status}
Progress : {bar} {int(progress_pct)}%
------------------------------------------------------------------"""
        print(card)

    @staticmethod
    def render_disagreement_warning(gemini_ans: str, local_ans: str):
        msg = f"""
⚠ AI MODEL DISAGREEMENT

Gemini      : {gemini_ans}
Local model : {local_ans}

Review required by human operator.
"""
        print(msg)
