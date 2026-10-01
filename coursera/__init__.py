"""Coursera domain package for Coursera automation agent."""

from coursera.course import CourseManager, CourseInfo
from coursera.modules import ModuleManager, ModuleInfo
from coursera.lessons import LessonManager, LessonInfo
from coursera.navigation import NavigationManager
from coursera.detectors import ContentDetector, PageContentType
from coursera.completion import CompletionDetector

__all__ = [
    "CourseManager",
    "CourseInfo",
    "ModuleManager",
    "ModuleInfo",
    "LessonManager",
    "LessonInfo",
    "NavigationManager",
    "ContentDetector",
    "PageContentType",
    "CompletionDetector",
]
