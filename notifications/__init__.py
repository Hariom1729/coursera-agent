"""Notifications package for Coursera automation agent."""

from notifications.macos import MacOSNotifier
from notifications.terminal import TerminalNotifier

__all__ = ["MacOSNotifier", "TerminalNotifier"]
