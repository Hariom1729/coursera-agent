"""Unit tests for assessment parser and type inference."""

import pytest
from assessments.parser import AssessmentParser
from assessments.models import OptionItem, QuestionType, QuestionItem
from assessments.analyzer import AssessmentAnalyzer
from unittest.mock import MagicMock


def test_parser_clean_question_text():
    raw1 = "1. What is Python? (1 point)"
    clean1 = AssessmentParser.clean_question_text(raw1)
    assert clean1 == "What is Python?"

    raw2 = "Question 3) Which statement creates an array?"
    clean2 = AssessmentParser.clean_question_text(raw2)
    assert clean2 == "Which statement creates an array?"


def test_parser_clean_option_text():
    opt1 = "A. Lists are ordered"
    assert AssessmentParser.clean_option_text(opt1) == "Lists are ordered"

    opt2 = "B) Tuples are immutable"
    assert AssessmentParser.clean_option_text(opt2) == "Tuples are immutable"


def test_infer_question_type():
    parser = AssessmentParser()

    # True / False
    tf_opts = [OptionItem(label="A", text="True"), OptionItem(label="B", text="False")]
    assert parser.infer_question_type(None, tf_opts) == QuestionType.TRUE_FALSE

    # Standard Multiple Choice
    mc_opts = [OptionItem(label="A", text="Red"), OptionItem(label="B", text="Blue"), OptionItem(label="C", text="Green")]
    assert parser.infer_question_type(None, mc_opts) == QuestionType.MULTIPLE_CHOICE

    # Image based
    assert parser.infer_question_type(None, mc_opts, has_visuals=True) == QuestionType.IMAGE_BASED

    # Short text
    assert parser.infer_question_type(None, []) == QuestionType.SHORT_TEXT


def test_format_question_for_ai():
    analyzer = AssessmentAnalyzer(ai_router=MagicMock(), db_manager=MagicMock())
    q = QuestionItem(
        id="q1",
        assessment_id="a1",
        question_number=1,
        question_text="What is indentation in Python used for?",
        options=[
            OptionItem(label="A", text="Formatting only"),
            OptionItem(label="B", text="Defining block scope"),
        ],
    )
    formatted = analyzer.format_question_for_ai(q)
    assert "Question 1: What is indentation in Python used for?" in formatted
    assert "A. Formatting only" in formatted
    assert "B. Defining block scope" in formatted


def test_assessment_solver_initialization():
    from assessments.solver import AssessmentSolver
    solver = AssessmentSolver()
    assert len(solver.MODAL_CONTINUE_SELECTORS) > 0
    assert len(solver.SUBMIT_SELECTORS) > 0

