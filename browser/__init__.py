"""Browser automation package for Coursera automation agent."""

from browser.manager import BrowserManager
from browser.session import SessionManager
from browser.recovery import BrowserRecovery

__all__ = ["BrowserManager", "SessionManager", "BrowserRecovery"]
