"""SQLAlchemy ORM models for Coursera automation agent."""

from __future__ import annotations

import datetime
from datetime import timezone
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    slug = Column(String, index=True)
    url = Column(String, nullable=False)
    instructor = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    certificate_available = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan", order_by="Module.module_index")
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")


class Module(Base):
    __tablename__ = "modules"

    id = Column(String, primary_key=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    module_index = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan", order_by="Lesson.lesson_index")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(String, primary_key=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    module_id = Column(String, ForeignKey("modules.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    lesson_type = Column(String, default="other")  # video, reading, quiz, assignment, discussion, other
    lesson_index = Column(Integer, default=0)
    is_graded = Column(Boolean, default=False)
    status = Column(String, default="DISCOVERED")  # DISCOVERED, STARTED, PROCESSING, COMPLETED, FAILED, SKIPPED, WAITING_FOR_USER
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    course = relationship("Course", back_populates="lessons")
    module = relationship("Module", back_populates="lessons")
    progress_records = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String, nullable=False, index=True)
    module_id = Column(String, nullable=False, index=True)
    lesson_id = Column(String, ForeignKey("lessons.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    retry_count = Column(Integer, default=0)
    metadata_json = Column(Text, nullable=True)

    lesson = relationship("Lesson", back_populates="progress_records")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True)
    lesson_id = Column(String, ForeignKey("lessons.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    assessment_type = Column(String, default="quiz")  # quiz, assignment, exam, practice
    is_graded = Column(Boolean, default=False)
    total_questions = Column(Integer, default=0)
    confidence = Column(Float, default=1.0)
    requires_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    questions = relationship("Question", back_populates="assessment", cascade="all, delete-orphan", order_by="Question.question_number")


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True)
    assessment_id = Column(String, ForeignKey("assessments.id"), nullable=False, index=True)
    question_number = Column(Integer, default=1)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, default="multiple_choice")  # multiple_choice, multiple_select, true_false, short_text, matching, image_based
    options_json = Column(Text, nullable=True)  # JSON serialized list of options
    screenshot_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    assessment = relationship("Assessment", back_populates="questions")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String, index=True, nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=True, index=True)
    provider = Column(String, nullable=False)  # gemini, local, ensemble
    model = Column(String, nullable=False)
    prompt_version = Column(String, default="v1")
    response_json = Column(Text, nullable=False)
    candidate_answer = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    agreement = Column(Boolean, nullable=True)
    requires_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_hash_model", "content_hash", "model"),
    )


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id = Column(String, primary_key=True)
    course_id = Column(String, nullable=False, index=True)
    current_state = Column(String, default="START")
    last_module_id = Column(String, nullable=True)
    last_lesson_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="RUNNING")  # RUNNING, PAUSED, COMPLETED, FAILED


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))


class AppError(Base):
    __tablename__ = "errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=True, index=True)
    error_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    context_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
