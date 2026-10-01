"""Coursera session detection and login management."""

from __future__ import annotations

import asyncio
import logging
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class SessionManager:
    """Detects Coursera login state and prompts user when manual authentication is needed."""

    LOGIN_INDICATOR_SELECTORS = [
        '[data-e2e="header-profile-menu"]',
        'button[aria-label*="profile" i]',
        'button[aria-label*="account" i]',
        'a[href*="/my-learning"]',
        'a[href*="/account-profile"]',
        'a[data-click-key*="my_learning"]',
        '.cds-avatar',
        'button[data-testid="header-profile-avatar-button"]',
        'button[aria-label*="User Menu" i]',
    ]

    LOGGED_OUT_SELECTORS = [
        'a[data-e2e="header-login-button"]',
        'a[href*="/login"]',
        'a[href*="/signup"]',
        'button:has-text("Log In")',
        'a:has-text("Log In")',
        'a:has-text("Join for Free")',
        'button:has-text("Join for Free")',
        'a:has-text("Join for free")',
        'button:has-text("Join for free")',
    ]

    def __init__(self, login_timeout_seconds: int = 300):
        self.login_timeout_seconds = login_timeout_seconds

    async def is_logged_in(self, page: Page) -> bool:
        """Check if current page shows an active logged-in Coursera session."""
        try:
            # 1. If any prominent login/join button is visible, user is definitely logged out
            for selector in self.LOGGED_OUT_SELECTORS:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return False

            # 2. Check for authenticated user indicators (avatar, profile menu, user dropdown)
            for selector in self.LOGIN_INDICATOR_SELECTORS:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return True

            # 3. Check cookies specifically for authenticated CAUTH session token
            cookies = await page.context.cookies()
            auth_cookies = [
                c for c in cookies 
                if c.get("name") == "CAUTH" and len(c.get("value", "")) > 15
            ]
            if auth_cookies:
                return True

            return False
        except Exception as e:
            logger.debug(f"Error checking login state: {e}")
            return False

    async def ensure_authenticated(self, page: Page) -> bool:
        """Verify user is logged into Coursera, waiting for manual login if required."""
        current_url = page.url
        if "coursera.org" not in current_url:
            logger.info("Navigating to Coursera home to verify authentication...")
            await page.goto("https://www.coursera.org/", wait_until="domcontentloaded")
            await asyncio.sleep(2)

        if await self.is_logged_in(page):
            logger.info("Active Coursera session verified. User is logged in.")
            return True

        print("\n" + "=" * 60)
        print(" [!] MANUAL COURSERA LOGIN REQUIRED")
        print("=" * 60)
        print("The agent detected you are not currently logged in to Coursera.")
        print("Please log in using the open browser window.")
        print("The session will be preserved in your browser profile directory.")
        print(f"Waiting up to {self.login_timeout_seconds} seconds for login to complete...")
        print("=" * 60 + "\n")

        elapsed = 0
        poll_interval = 3
        while elapsed < self.login_timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            if await self.is_logged_in(page):
                print("\n[✓] Login detected successfully! Resuming automation...\n")
                logger.info("User login successfully detected.")
                return True

            if elapsed % 15 == 0:
                print(f"Still waiting for login... ({elapsed}/{self.login_timeout_seconds}s)")

        raise TimeoutError("Authentication timeout: User did not log in within the allotted time.")
