"""Data access repositories for Coursera agent entities."""

from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Course,
    Module,
    Lesson,
    LessonProgress,
    Assessment,
    Question,
    AIAnalysis,
    AutomationRun,
    Event,
    AppError,
)


class CourseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, course_id: str) -> Optional[Course]:
        res = await self.session.execute(select(Course).where(Course.id == course_id))
        return res.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Optional[Course]:
        res = await self.session.execute(select(Course).where(Course.url == url))
        return res.scalar_one_or_none()

    async def upsert_course(
        self,
        course_id: str,
        title: str,
        url: str,
        slug: Optional[str] = None,
        instructor: Optional[str] = None,
    ) -> Course:
        course = await self.get_by_id(course_id)
        if not course:
            course = Course(
                id=course_id,
                title=title,
                url=url,
                slug=slug or "",
                instructor=instructor or "",
            )
            self.session.add(course)
        else:
            course.title = title
            course.url = url
            if slug:
                course.slug = slug
            if instructor:
                course.instructor = instructor
        await self.session.flush()
        return course

    async def mark_completed(self, course_id: str, certificate_available: bool = False):
        await self.session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(is_completed=True, certificate_available=certificate_available)
        )
        await self.session.flush()


class ModuleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_modules(self, course_id: str) -> List[Module]:
        res = await self.session.execute(
            select(Module).where(Module.course_id == course_id).order_by(Module.module_index)
        )
        return list(res.scalars().all())

    async def upsert_module(
        self,
        module_id: str,
        course_id: str,
        title: str,
        module_index: int,
    ) -> Module:
        res = await self.session.execute(select(Module).where(Module.id == module_id))
        module = res.scalar_one_or_none()
        if not module:
            module = Module(
                id=module_id,
                course_id=course_id,
                title=title,
                module_index=module_index,
            )
            self.session.add(module)
        else:
            module.title = title
            module.module_index = module_index
        await self.session.flush()
        return module

    async def mark_completed(self, module_id: str):
        await self.session.execute(
            update(Module).where(Module.id == module_id).values(is_completed=True)
        )
        await self.session.flush()


class LessonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, lesson_id: str) -> Optional[Lesson]:
        res = await self.session.execute(select(Lesson).where(Lesson.id == lesson_id))
        return res.scalar_one_or_none()

    async def get_lessons_for_module(self, module_id: str) -> List[Lesson]:
        res = await self.session.execute(
            select(Lesson).where(Lesson.module_id == module_id).order_by(Lesson.lesson_index)
        )
        return list(res.scalars().all())

    async def get_all_for_course(self, course_id: str) -> List[Lesson]:
        res = await self.session.execute(
            select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.lesson_index)
        )
        return list(res.scalars().all())

    async def upsert_lesson(
        self,
        lesson_id: str,
        course_id: str,
        module_id: str,
        title: str,
        url: str,
        lesson_type: str = "other",
        lesson_index: int = 0,
        is_graded: bool = False,
    ) -> Lesson:
        lesson = await self.get_by_id(lesson_id)
        if not lesson:
            lesson = Lesson(
                id=lesson_id,
                course_id=course_id,
                module_id=module_id,
                title=title,
                url=url,
                lesson_type=lesson_type,
                lesson_index=lesson_index,
                is_graded=is_graded,
                status="DISCOVERED",
            )
            self.session.add(lesson)
        else:
            lesson.title = title
            lesson.url = url
            lesson.lesson_type = lesson_type
            lesson.lesson_index = lesson_index
            lesson.is_graded = is_graded
        await self.session.flush()
        return lesson

    async def update_status(self, lesson_id: str, status: str):
        await self.session.execute(
            update(Lesson).where(Lesson.id == lesson_id).values(status=status)
        )
        await self.session.flush()

    async def record_progress(
        self,
        course_id: str,
        module_id: str,
        lesson_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LessonProgress:
        progress = LessonProgress(
            course_id=course_id,
            module_id=module_id,
            lesson_id=lesson_id,
            status=status,
            completed_at=datetime.datetime.now(datetime.timezone.utc) if status == "COMPLETED" else None,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.session.add(progress)
        await self.update_status(lesson_id, status)
        await self.session.flush()
        return progress


class AssessmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_assessment(
        self,
        assessment_id: str,
        lesson_id: Optional[str],
        title: str,
        assessment_type: str,
        is_graded: bool,
        total_questions: int,
        confidence: float,
        requires_review: bool,
    ) -> Assessment:
        res = await self.session.execute(select(Assessment).where(Assessment.id == assessment_id))
        assessment = res.scalar_one_or_none()
        if not assessment:
            assessment = Assessment(
                id=assessment_id,
                lesson_id=lesson_id,
                title=title,
                assessment_type=assessment_type,
                is_graded=is_graded,
                total_questions=total_questions,
                confidence=confidence,
                requires_review=requires_review,
            )
            self.session.add(assessment)
        else:
            assessment.title = title
            assessment.assessment_type = assessment_type
            assessment.is_graded = is_graded
            assessment.total_questions = total_questions
            assessment.confidence = confidence
            assessment.requires_review = requires_review
        await self.session.flush()
        return assessment

    async def save_question(
        self,
        question_id: str,
        assessment_id: str,
        question_number: int,
        question_text: str,
        question_type: str,
        options: Optional[List[Dict[str, Any]]] = None,
        screenshot_path: Optional[str] = None,
    ) -> Question:
        res = await self.session.execute(select(Question).where(Question.id == question_id))
        q = res.scalar_one_or_none()
        options_json = json.dumps(options) if options else None
        if not q:
            q = Question(
                id=question_id,
                assessment_id=assessment_id,
                question_number=question_number,
                question_text=question_text,
                question_type=question_type,
                options_json=options_json,
                screenshot_path=screenshot_path,
            )
            self.session.add(q)
        else:
            q.question_text = question_text
            q.question_type = question_type
            q.options_json = options_json
            if screenshot_path:
                q.screenshot_path = screenshot_path
        await self.session.flush()
        return q


class AICacheRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cached_analysis(self, content_hash: str, model: str) -> Optional[AIAnalysis]:
        res = await self.session.execute(
            select(AIAnalysis)
            .where(AIAnalysis.content_hash == content_hash, AIAnalysis.model == model)
            .order_by(desc(AIAnalysis.created_at))
        )
        return res.scalar_one_or_none()

    async def save_analysis(
        self,
        content_hash: str,
        provider: str,
        model: str,
        response_json: str,
        candidate_answer: Optional[str] = None,
        confidence: float = 0.0,
        agreement: Optional[bool] = None,
        requires_review: bool = False,
        question_id: Optional[str] = None,
        prompt_version: str = "v1",
    ) -> AIAnalysis:
        analysis = AIAnalysis(
            content_hash=content_hash,
            question_id=question_id,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            response_json=response_json,
            candidate_answer=candidate_answer,
            confidence=confidence,
            agreement=agreement,
            requires_review=requires_review,
        )
        self.session.add(analysis)
        await self.session.flush()
        return analysis


class AutomationRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_run(self, run_id: str, course_id: str) -> AutomationRun:
        run = AutomationRun(
            id=run_id,
            course_id=course_id,
            current_state="START",
            status="RUNNING",
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_state(
        self,
        run_id: str,
        state: str,
        last_module_id: Optional[str] = None,
        last_lesson_id: Optional[str] = None,
        status: Optional[str] = None,
    ):
        values: Dict[str, Any] = {"current_state": state}
        if last_module_id is not None:
            values["last_module_id"] = last_module_id
        if last_lesson_id is not None:
            values["last_lesson_id"] = last_lesson_id
        if status is not None:
            values["status"] = status
            if status in ("COMPLETED", "FAILED"):
                values["ended_at"] = datetime.datetime.utcnow()

        await self.session.execute(
            update(AutomationRun).where(AutomationRun.id == run_id).values(**values)
        )
        await self.session.flush()

    async def get_latest_run(self, course_id: Optional[str] = None) -> Optional[AutomationRun]:
        stmt = select(AutomationRun).order_by(desc(AutomationRun.started_at))
        if course_id:
            stmt = stmt.where(AutomationRun.course_id == course_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def log_event(self, run_id: Optional[str], event_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        ev = Event(
            run_id=run_id,
            event_type=event_type,
            message=message,
            details_json=json.dumps(details) if details else None,
        )
        self.session.add(ev)
        await self.session.flush()

    async def log_error(self, run_id: Optional[str], error_type: str, message: str, stack_trace: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        err = AppError(
            run_id=run_id,
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context_json=json.dumps(context) if context else None,
        )
        self.session.add(err)
        await self.session.flush()
