"""ExamMarker Phase 1 CLI: mark one scanned script end-to-end, no DB/web.

    python -m app.cli mark --pdf x.pdf --scheme scheme.txt --course "CSC301" \\
        --total 100 --out report.json

Writes report.json (Part A, the validated MarkingReport), report.txt (Part
B, human-readable) and report.xlsx alongside --out. See PROJECT_SPEC.md,
"BUILD PHASES" -> Phase 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.export.excel import export_report_to_excel
from app.marking import preprocess
from app.marking.engine import mark_script
from app.marking.prompt import render_prompt


def cmd_mark(args: argparse.Namespace, client=None) -> int:
    page_images = preprocess.preprocess_pdf(args.pdf, dpi=args.dpi)
    marking_scheme_text = Path(args.scheme).read_text(encoding="utf-8")
    question_paper_text = Path(args.paper).read_text(encoding="utf-8") if args.paper else ""

    system_prompt = render_prompt(
        course_code=args.course,
        course_title=args.course_title or args.course,
        total_marks=args.total,
        selection_rule=args.selection_rule,
        question_paper_text=question_paper_text,
        marking_scheme_text=marking_scheme_text,
        grading_scale=args.grading_scale,
        special_instructions=args.special_instructions,
        mode=args.mode,
        language=args.language,
        review_threshold=args.review_threshold,
    )

    result = mark_script(page_images=page_images, system_prompt=system_prompt, client=client)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not result.success:
        error_payload = {
            "success": False,
            "attempts": result.attempts,
            "error": result.error,
            "raw_output": result.raw_text,
        }
        out_path.write_text(json.dumps(error_payload, indent=2), encoding="utf-8")
        print(f"Marking FAILED after {result.attempts} attempt(s): {result.error}", file=sys.stderr)
        return 1

    out_path.write_text(result.report.model_dump_json(indent=2), encoding="utf-8")

    txt_path = out_path.with_suffix(".txt")
    txt_path.write_text(result.human_readable, encoding="utf-8")

    xlsx_path = out_path.with_suffix(".xlsx")
    export_report_to_excel(result.report, xlsx_path)

    print(f"Marked successfully in {result.attempts} attempt(s).")
    print(f"  JSON:  {out_path}")
    print(f"  Text:  {txt_path}")
    print(f"  Excel: {xlsx_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="ExamMarker CLI: mark a scanned script against a marking scheme.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    mark_parser = subparsers.add_parser("mark", help="Mark one scanned script PDF.")
    mark_parser.add_argument("--pdf", required=True, type=Path, help="Path to the scanned script PDF.")
    mark_parser.add_argument(
        "--scheme", required=True, type=Path, help="Path to the marking scheme text file."
    )
    mark_parser.add_argument(
        "--course", required=True, help="Course code (also used as title unless --course-title is given)."
    )
    mark_parser.add_argument("--total", required=True, type=int, help="Total marks for the exam.")
    mark_parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for the JSON report (.txt and .xlsx are written alongside it).",
    )
    mark_parser.add_argument("--course-title", default=None, help="Course title, if different from --course.")
    mark_parser.add_argument("--paper", default=None, type=Path, help="Path to the question paper text file.")
    mark_parser.add_argument(
        "--selection-rule", default="All questions compulsory", help="e.g. 'Answer any 4 of 6 questions'."
    )
    mark_parser.add_argument("--grading-scale", default=None)
    mark_parser.add_argument("--special-instructions", default=None)
    mark_parser.add_argument("--mode", default="MARK", choices=["MARK", "REMARK"])
    mark_parser.add_argument("--language", default="English")
    mark_parser.add_argument("--review-threshold", default=3, type=int)
    mark_parser.add_argument("--dpi", default=300, type=int, help="PDF rasterization DPI (default 300).")
    mark_parser.set_defaults(func=cmd_mark)

    return parser


def main(argv: list[str] | None = None, client=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args, client=client)


if __name__ == "__main__":
    sys.exit(main())
