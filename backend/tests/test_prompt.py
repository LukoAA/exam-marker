import re

import pytest

from app.marking.prompt import render_prompt

BASE_KWARGS = dict(
    course_code="CSC301",
    course_title="Data Structures",
    total_marks=100,
    selection_rule="Answer any 4 of 6 questions",
    question_paper_text="1. Define a binary search tree...",
    marking_scheme_text="Q1 (10 marks):\n  1a. Definition ..... 2 marks",
)


def test_render_prompt_fills_all_provided_placeholders():
    rendered = render_prompt(
        **BASE_KWARGS,
        grading_scale="A: 70-100, B: 60-69",
        special_instructions="Accept pseudocode in any style.",
        mode="MARK",
        language="English",
        review_threshold=5,
    )

    assert "CSC301" in rendered
    assert "Data Structures" in rendered
    assert "100" in rendered
    assert "Answer any 4 of 6 questions" in rendered
    assert "1. Define a binary search tree..." in rendered
    assert "1a. Definition ..... 2 marks" in rendered
    assert "A: 70-100, B: 60-69" in rendered
    assert "Accept pseudocode in any style." in rendered
    assert "5" in rendered


def test_render_prompt_applies_defaults_when_optional_fields_omitted():
    rendered = render_prompt(**BASE_KWARGS)

    assert "MARK" in rendered
    assert "3" in rendered  # default REVIEW_THRESHOLD
    assert "English" in rendered
    assert "Not provided — report raw score and percentage only" in rendered
    assert "None" in rendered


def test_render_prompt_leaves_no_unreplaced_placeholders():
    rendered = render_prompt(**BASE_KWARGS)

    assert re.findall(r"\{\{[^}]*\}\}", rendered) == []


def test_render_prompt_excludes_implementation_notes_section():
    rendered = render_prompt(**BASE_KWARGS)

    assert "IMPLEMENTATION NOTES FOR YOUR SOFTWARE" not in rendered
    assert "One script per API request" not in rendered


def test_render_prompt_rejects_invalid_mode():
    with pytest.raises(ValueError, match="mode must be"):
        render_prompt(**BASE_KWARGS, mode="INVALID")


def test_render_prompt_remark_mode_is_injected():
    rendered = render_prompt(**BASE_KWARGS, mode="REMARK")

    assert 'only when REMARK = "REMARK"' in rendered
