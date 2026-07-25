"""Claude marking engine: sends preprocessed page images + the injected
prompt to the Anthropic API, extracts and validates Part A JSON, and
independently recomputes the score. See PROJECT_SPEC.md "THE MARKING
ENGINE" step 3.

Score recomputation happens BEFORE the final schema validation, not after:
schemas.MarkingReport hard-rejects a question whose awarded > max_marks, but
an over-max score is exactly the kind of model arithmetic slip this step
exists to fix. So we clamp/recompute on the raw dict first, then validate
the corrected data — genuine structural problems (missing fields, bad
enum values, unparsable JSON) are what trigger the retry-then-fail path.
"""
from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass

from anthropic import Anthropic
from PIL import Image
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import MarkingReport

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0
MAX_TOKENS = 16000
MAX_ATTEMPTS = 2
MARK_INSTRUCTION = "Mark this script."

CORRECTIVE_INSTRUCTION_TEMPLATE = (
    "Your previous response's Part A JSON failed validation with this error:\n"
    "{error}\n\n"
    "Re-emit the FULL response (Part A JSON and Part B human-readable report), "
    "correcting the JSON so it strictly matches the required schema. Do not "
    "change any marking decisions — only fix the JSON's structure/types."
)

_FENCED_JSON_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_PART_A_MARKER_RE = re.compile(r"part\s*a", re.IGNORECASE)
_PART_B_MARKER_RE = re.compile(r"part\s*b", re.IGNORECASE)


@dataclass
class MarkingResult:
    success: bool
    report: MarkingReport | None
    human_readable: str
    raw_text: str
    attempts: int
    error: str | None = None


def _build_image_blocks(page_images: list[Image.Image]) -> list[dict]:
    blocks = []
    for image in page_images:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        encoded = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
        blocks.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": encoded},
            }
        )
    return blocks


def _response_text(response) -> str:
    """Concatenate all text blocks of an Anthropic Messages API response."""
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def _extract_balanced_object(text: str, start: int) -> str:
    """Return the substring of text spanning the balanced {...} object that
    starts at index `start`, respecting string literals so braces inside
    quoted text don't throw off the depth count."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON object in model response")


def extract_json_block(text: str) -> str:
    """Pull the Part A JSON object out of the model's raw response text.

    Prefers a fenced ```json``` block; otherwise finds the first balanced
    {...} object after a "Part A" marker (or anywhere, if there is none).
    """
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        return fenced.group(1).strip()

    search_start = 0
    part_a_marker = _PART_A_MARKER_RE.search(text)
    if part_a_marker:
        search_start = part_a_marker.end()

    brace_start = text.find("{", search_start)
    if brace_start == -1:
        raise ValueError("no JSON object found in model response")

    return _extract_balanced_object(text, brace_start)


def extract_human_readable(text: str, json_block: str) -> str:
    """Return Part B: everything after the JSON block (or after a "Part B"
    marker, if present), with surrounding labels/code fences stripped."""
    marker = _PART_B_MARKER_RE.search(text)
    if marker:
        remainder = text[marker.end() :]
    else:
        idx = text.find(json_block)
        remainder = text[idx + len(json_block) :] if idx != -1 else ""

    remainder = re.sub(r"^\s*[—:\-]*\s*", "", remainder)
    remainder = re.sub(r"^```(?:\w+)?\s*", "", remainder)
    remainder = re.sub(r"```\s*$", "", remainder.strip())
    return remainder.strip()


def _recompute_totals(data: dict) -> None:
    """Independently recompute scores in plain Python — never trust the
    model's own arithmetic. Clamps each question's awarded to
    [0, max_marks], then recomputes total_awarded and percentage from the
    now-clamped per-question scores plus the MCQ score.
    """
    total = 0.0
    for question in data.get("questions", []):
        max_marks = float(question.get("max_marks") or 0)
        awarded = float(question.get("awarded") or 0)
        clamped = max(0.0, min(awarded, max_marks))
        question["awarded"] = clamped
        total += clamped

    mcq = data.get("mcq_section") or {}
    if mcq.get("present"):
        total += float(mcq.get("score") or 0)

    total_possible = float(data.get("total_possible") or 0)
    data["total_awarded"] = total
    data["percentage"] = round((total / total_possible) * 100, 2) if total_possible else 0.0


def mark_script(
    *,
    page_images: list[Image.Image],
    system_prompt: str,
    client: Anthropic | None = None,
) -> MarkingResult:
    """Mark one script: one Anthropic Messages API call (one retry on schema
    validation failure), Part A JSON extraction + validation + recompute,
    Part B human-readable extraction.
    """
    if client is None:
        client = Anthropic(api_key=get_settings().ANTHROPIC_API_KEY)

    messages: list[dict] = [
        {
            "role": "user",
            "content": _build_image_blocks(page_images) + [{"type": "text", "text": MARK_INSTRUCTION}],
        }
    ]

    raw_text = ""
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=messages,
        )
        raw_text = _response_text(response)

        try:
            json_block = extract_json_block(raw_text)
            data = json.loads(json_block)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = f"JSON extraction/parse failed: {exc}"
        else:
            _recompute_totals(data)
            try:
                report = MarkingReport.model_validate(data)
            except ValidationError as exc:
                last_error = f"schema validation failed: {exc}"
            else:
                return MarkingResult(
                    success=True,
                    report=report,
                    human_readable=extract_human_readable(raw_text, json_block),
                    raw_text=raw_text,
                    attempts=attempt,
                )

        if attempt < MAX_ATTEMPTS:
            messages.append({"role": "assistant", "content": raw_text})
            messages.append(
                {
                    "role": "user",
                    "content": CORRECTIVE_INSTRUCTION_TEMPLATE.format(error=last_error),
                }
            )

    return MarkingResult(
        success=False,
        report=None,
        human_readable="",
        raw_text=raw_text,
        attempts=MAX_ATTEMPTS,
        error=last_error,
    )
