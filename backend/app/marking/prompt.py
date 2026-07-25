"""Loads prompt_v3.md and injects course/scheme/mode values into the marking
system prompt. See PROJECT_SPEC.md, "THE MARKING ENGINE" step 2.

prompt_v3.md is authored by the lecturer/spec owner, not generated code, and
its placeholder tokens are written for human readability rather than as
clean machine-parseable `{{VAR}}` names (e.g. `{{GRADING_SCALE or "Not
provided..."}}`, `{{LANGUAGE, default English}}`). Each placeholder below is
matched by its leading identifier so the descriptive trailing text inside
the braces doesn't need to match exactly.
"""
from __future__ import annotations

import re
from pathlib import Path

PROMPT_PATH = Path(__file__).parent / "prompt_v3.md"
IMPLEMENTATION_NOTES_MARKER = "## IMPLEMENTATION NOTES FOR YOUR SOFTWARE"

DEFAULT_MODE = "MARK"
DEFAULT_REVIEW_THRESHOLD = 3
DEFAULT_LANGUAGE = "English"
DEFAULT_GRADING_SCALE = "Not provided — report raw score and percentage only"
DEFAULT_SPECIAL_INSTRUCTIONS = "None"

_PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}", re.DOTALL)


def _load_template() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_text, _, _ = text.partition(IMPLEMENTATION_NOTES_MARKER)
    return prompt_text.strip()


def _replace_placeholder(text: str, identifier: str, value: str) -> str:
    pattern = re.compile(r"\{\{" + identifier + r"\b.*?\}\}", re.DOTALL)
    return pattern.sub(lambda _match: value, text)


def render_prompt(
    *,
    course_code: str,
    course_title: str,
    total_marks: float,
    selection_rule: str,
    question_paper_text: str,
    marking_scheme_text: str,
    grading_scale: str | None = None,
    special_instructions: str | None = None,
    mode: str = DEFAULT_MODE,
    language: str = DEFAULT_LANGUAGE,
    review_threshold: int = DEFAULT_REVIEW_THRESHOLD,
) -> str:
    """Load prompt_v3.md's system prompt (excluding the trailing
    "IMPLEMENTATION NOTES FOR YOUR SOFTWARE" section, which is explicitly
    marked "not part of the prompt") and fill in every {{PLACEHOLDER}}.

    Raises ValueError if mode isn't "MARK"/"REMARK", or if any {{...}}
    placeholder is left unreplaced (a sign prompt_v3.md gained a placeholder
    this function doesn't know about).
    """
    if mode not in ("MARK", "REMARK"):
        raise ValueError(f"mode must be 'MARK' or 'REMARK', got {mode!r}")

    text = _load_template()

    text = _replace_placeholder(text, "COURSE_CODE", course_code)
    text = _replace_placeholder(text, "COURSE_TITLE", course_title)
    text = _replace_placeholder(text, "TOTAL_MARKS", str(total_marks))
    text = _replace_placeholder(text, "GRADING_SCALE", grading_scale or DEFAULT_GRADING_SCALE)
    text = _replace_placeholder(
        text, "SPECIAL_INSTRUCTIONS", special_instructions or DEFAULT_SPECIAL_INSTRUCTIONS
    )
    text = _replace_placeholder(text, "MODE", mode)
    text = _replace_placeholder(text, "LANGUAGE", language)
    text = _replace_placeholder(text, "FULL_QUESTION_PAPER_TEXT", question_paper_text)
    text = _replace_placeholder(text, "OFFICIAL_MARKING_SCHEME", marking_scheme_text)
    text = _replace_placeholder(text, "REVIEW_THRESHOLD", str(review_threshold))

    # "Selection rule: {{...}}" has no leading identifier of its own (the
    # braces just contain an example), so match on the surrounding label.
    selection_rule_pattern = re.compile(r"(Selection rule:\s*)\{\{.*?\}\}", re.DOTALL)
    text = selection_rule_pattern.sub(lambda m: m.group(1) + selection_rule, text)

    unreplaced = _PLACEHOLDER_RE.findall(text)
    if unreplaced:
        raise ValueError(f"prompt_v3.md has unreplaced placeholders: {unreplaced}")

    return text
