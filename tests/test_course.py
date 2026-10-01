"""Unit tests for Coursera course URL parsing and lesson classification."""

import pytest
from coursera.course import CourseManager
from coursera.lessons import LessonManager


def test_slug_extraction():
    url1 = "https://www.coursera.org/learn/python-basics/home/welcome"
    assert CourseManager.extract_slug_from_url(url1) == "python-basics"

    url2 = "https://www.coursera.org/learn/machine-learning"
    assert CourseManager.extract_slug_from_url(url2) == "machine-learning"

    url3 = "https://www.coursera.org/learn/deep-neural-networks?tab=notes"
    assert CourseManager.extract_slug_from_url(url3) == "deep-neural-networks"


def test_lesson_type_classification():
    # Video
    t1, g1 = LessonManager.classify_lesson_type(
        url="https://www.coursera.org/learn/python/lecture/abc/intro",
        text="Video • 8 min",
    )
    assert t1 == "video"
    assert g1 is False

    # Reading
    t2, g2 = LessonManager.classify_lesson_type(
        url="https://www.coursera.org/learn/python/supplement/def/reading-guide",
        text="Reading • 10 min",
    )
    assert t2 == "reading"
    assert g2 is False

    # Practice Quiz
    t3, g3 = LessonManager.classify_lesson_type(
        url="https://www.coursera.org/learn/python/quiz/ghi/practice-review",
        text="Practice Quiz • 30 min",
    )
    assert t3 == "quiz"
    assert g3 is False

    # Graded Quiz
    t4, g4 = LessonManager.classify_lesson_type(
        url="https://www.coursera.org/learn/python/quiz/jkl/week-1-quiz",
        text="Graded Quiz • 45 min",
    )
    assert t4 == "quiz"
    assert g4 is True

    # Graded Exam
    t5, g5 = LessonManager.classify_lesson_type(
        url="https://www.coursera.org/learn/python/exam/mno/final-exam",
        text="Final Graded Assessment",
    )
    assert t5 == "assessment"
    assert g5 is True
