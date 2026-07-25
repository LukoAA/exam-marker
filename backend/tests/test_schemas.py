import copy

import pytest
from pydantic import ValidationError

from app.schemas import MarkingReport

VALID_REPORT = {
    "student_name": "Jane Doe",
    "matric_number": "CSC/2021/001",
    "course_code": "CSC301",
    "needs_human_review": False,
    "review_reasons": [],
    "questions": [
        {
            "question": "1",
            "attempted": True,
            "max_marks": 10,
            "awarded": 7.5,
            "provisional": False,
            "mark_points": [
                {
                    "scheme_point": "1a — definition of osmosis (2 marks)",
                    "decision": "AWARDED",
                    "marks": 2,
                    "evidence": "student wrote: 'movement of water molecules...'",
                    "note": "",
                },
                {
                    "scheme_point": "1b — three characteristics @ 1 (3 marks)",
                    "decision": "PARTIAL",
                    "marks": 2,
                    "evidence": "student gave two of three characteristics",
                    "note": "missing the third characteristic",
                },
            ],
            "strengths": "Clear definition and good use of terminology.",
            "missing_points": "Third characteristic omitted.",
            "errors": "None.",
            "legibility_flags": [],
        }
    ],
    "mcq_section": {
        "present": False,
        "answer_string": "",
        "correct": 0,
        "wrong": 0,
        "blank": 0,
        "ambiguous": 0,
        "score": 0,
    },
    "page_anomalies": [
        {
            "page": 4,
            "type": "rotated",
            "detail": "Page scanned upside down; content read correctly regardless.",
            "affected_questions": ["3"],
        }
    ],
    "identity_anomalies": [],
    "total_awarded": 7.5,
    "total_possible": 10,
    "percentage": 75,
    "grade": "B",
    "low_confidence_sections": [
        {
            "page": 2,
            "question": "3",
            "text": "[ILLEGIBLE: 4 words]",
            "impact": "up to 2 marks undetermined",
        }
    ],
    "overall_feedback": {
        "concepts_understood": "Osmosis fundamentals.",
        "weak_areas": "Detailed characteristics.",
        "topics_to_revise": "Cell membrane transport.",
        "summary": "Solid grasp of core concept, needs more depth.",
    },
}


def test_valid_report_parses():
    report = MarkingReport.model_validate(VALID_REPORT)

    assert report.student_name == "Jane Doe"
    assert report.questions[0].awarded == 7.5
    assert report.remark is None


def test_valid_report_with_remark_object_parses():
    payload = copy.deepcopy(VALID_REPORT)
    payload["remark"] = {
        "disputed_questions": ["1"],
        "original_score": 7.5,
        "new_score": 8.5,
        "change_justification": "1b characteristic 3 was present but illegible on first pass.",
        "appeal_upheld": "partial",
    }

    report = MarkingReport.model_validate(payload)

    assert report.remark is not None
    assert report.remark.appeal_upheld == "partial"


def test_question_awarded_exceeding_max_marks_is_rejected():
    payload = copy.deepcopy(VALID_REPORT)
    payload["questions"][0]["awarded"] = 15  # max_marks is 10

    with pytest.raises(ValidationError, match="exceeds max_marks"):
        MarkingReport.model_validate(payload)


def test_total_awarded_exceeding_total_possible_is_rejected():
    payload = copy.deepcopy(VALID_REPORT)
    payload["total_awarded"] = 12
    payload["total_possible"] = 10

    with pytest.raises(ValidationError, match="exceeds total_possible"):
        MarkingReport.model_validate(payload)


def test_invalid_mark_point_decision_is_rejected():
    payload = copy.deepcopy(VALID_REPORT)
    payload["questions"][0]["mark_points"][0]["decision"] = "MAYBE"

    with pytest.raises(ValidationError):
        MarkingReport.model_validate(payload)


def test_unknown_top_level_field_is_rejected():
    payload = copy.deepcopy(VALID_REPORT)
    payload["unexpected_field"] = "surprise"

    with pytest.raises(ValidationError):
        MarkingReport.model_validate(payload)


def test_missing_required_field_is_rejected():
    payload = copy.deepcopy(VALID_REPORT)
    del payload["overall_feedback"]

    with pytest.raises(ValidationError):
        MarkingReport.model_validate(payload)
