import json
from types import SimpleNamespace

import pytest
from PIL import Image

from app.marking import engine


def _valid_report_dict(awarded=7, max_marks=10, total_possible=10):
    return {
        "student_name": "Jane Doe",
        "matric_number": "CSC/2021/001",
        "course_code": "CSC301",
        "needs_human_review": False,
        "review_reasons": [],
        "questions": [
            {
                "question": "1",
                "attempted": True,
                "max_marks": max_marks,
                "awarded": awarded,
                "provisional": False,
                "mark_points": [
                    {
                        "scheme_point": "1a — definition (2 marks)",
                        "decision": "AWARDED",
                        "marks": 2,
                        "evidence": "student wrote: '...'",
                        "note": "",
                    }
                ],
                "strengths": "Good.",
                "missing_points": "None.",
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
        "page_anomalies": [],
        "identity_anomalies": [],
        # Deliberately wrong; mark_script must recompute these, not trust them.
        "total_awarded": 999,
        "total_possible": total_possible,
        "percentage": 999,
        "grade": "B",
        "low_confidence_sections": [],
        "overall_feedback": {
            "concepts_understood": "Understands the core concept.",
            "weak_areas": "Detail depth.",
            "topics_to_revise": "Cell membrane transport.",
            "summary": "Solid grasp, needs more depth.",
        },
    }


def _full_response_text(report_dict: dict, fenced: bool) -> str:
    json_text = json.dumps(report_dict, indent=2)
    json_block = f"```json\n{json_text}\n```" if fenced else json_text
    return (
        "**Part A — JSON (for the software):**\n\n"
        f"{json_block}\n\n"
        "**Part B — Human-readable report:**\n\n"
        "=================================================\n"
        "STUDENT EXAMINATION REPORT\n"
        "=================================================\n"
        "Student Name: Jane Doe\n"
        "TOTAL: 7/10\n"
    )


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]):
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


class FakeAnthropic:
    def __init__(self, responses: list[SimpleNamespace]):
        self.messages = FakeMessages(responses)


@pytest.fixture
def page_images():
    return [Image.new("RGB", (20, 20), color="white")]


def test_mark_script_parses_plain_json_response(page_images):
    text = _full_response_text(_valid_report_dict(), fenced=False)
    client = FakeAnthropic([_text_response(text)])

    result = engine.mark_script(page_images=page_images, system_prompt="sys", client=client)

    assert result.success is True
    assert result.attempts == 1
    assert result.report is not None
    assert result.report.student_name == "Jane Doe"
    assert "STUDENT EXAMINATION REPORT" in result.human_readable
    assert len(client.messages.calls) == 1


def test_mark_script_parses_fenced_json_response(page_images):
    text = _full_response_text(_valid_report_dict(), fenced=True)
    client = FakeAnthropic([_text_response(text)])

    result = engine.mark_script(page_images=page_images, system_prompt="sys", client=client)

    assert result.success is True
    assert result.attempts == 1
    assert result.report.course_code == "CSC301"


def test_mark_script_retries_once_on_invalid_json_then_succeeds(page_images):
    broken_text = (
        "**Part A — JSON (for the software):**\n\n"
        '```json\n{ "student_name": "Jane Doe", "course_code": "CSC301",\n```\n\n'
        "**Part B — Human-readable report:**\n...\n"
    )
    valid_text = _full_response_text(_valid_report_dict(), fenced=True)
    client = FakeAnthropic([_text_response(broken_text), _text_response(valid_text)])

    result = engine.mark_script(page_images=page_images, system_prompt="sys", client=client)

    assert result.success is True
    assert result.attempts == 2
    assert len(client.messages.calls) == 2
    # the retry call must carry a corrective instruction
    second_call_messages = client.messages.calls[1]["messages"]
    assert any(
        isinstance(m["content"], str) and "failed validation" in m["content"]
        for m in second_call_messages
    )


def test_mark_script_returns_failed_result_after_two_invalid_responses(page_images):
    broken_text = "no json here at all, sorry"
    client = FakeAnthropic([_text_response(broken_text), _text_response(broken_text)])

    result = engine.mark_script(page_images=page_images, system_prompt="sys", client=client)

    assert result.success is False
    assert result.attempts == 2
    assert result.report is None
    assert result.raw_text == broken_text
    assert result.error is not None
    assert len(client.messages.calls) == 2


def test_mark_script_caps_over_max_awarded_and_recomputes_totals(page_images):
    # Model claims 15/10 on the only question — must be clamped to 10, and
    # total_awarded/percentage recomputed in Python, not trusted from the JSON.
    report_dict = _valid_report_dict(awarded=15, max_marks=10, total_possible=10)
    text = _full_response_text(report_dict, fenced=True)
    client = FakeAnthropic([_text_response(text)])

    result = engine.mark_script(page_images=page_images, system_prompt="sys", client=client)

    assert result.success is True
    assert result.attempts == 1
    assert result.report.questions[0].awarded == 10
    assert result.report.total_awarded == 10
    assert result.report.percentage == 100.0


def test_extract_json_block_falls_back_to_balanced_braces_without_fence():
    report_dict = _valid_report_dict()
    text = "Part A — JSON:\n" + json.dumps(report_dict) + "\nPart B — text follows"

    extracted = engine.extract_json_block(text)

    assert json.loads(extracted) == report_dict


def test_extract_json_block_raises_when_no_json_present():
    with pytest.raises(ValueError):
        engine.extract_json_block("no json anywhere in this text")
