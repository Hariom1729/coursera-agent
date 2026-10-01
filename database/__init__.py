"""Database package for Coursera automation agent."""

from database.database import get_db_session, init_db, DatabaseSessionManager
from database.models import Base, Course, Module, Lesson, LessonProgress, Assessment, Question, AIAnalysis, AutomationRun, Event, AppError

__all__ = [
    "get_db_session",
    "init_db",
    "DatabaseSessionManager",
    "Base",
    "Course",
    "Module",
    "Lesson",
    "LessonProgress",
    "Assessment",
    "Question",
    "AIAnalysis",
    "AutomationRun",
    "Event",
    "AppError",
]
