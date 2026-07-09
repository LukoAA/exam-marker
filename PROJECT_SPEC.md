# CURSOR MASTER PROMPT — Automated Exam Marking System

## PROJECT OVERVIEW

Build **ExamMarker**: a web application that lets a university lecturer upload scanned
handwritten examination scripts, marks them automatically using the Anthropic Claude API
(vision), stores a fully auditable marking report per student, and exports an Excel
summary of the batch. Includes a review screen (scan side-by-side with mark breakdown),
lecturer overrides, and an appeal/re-mark workflow.

Developer environment: **Windows 10**, Cursor editor, PowerShell terminal.
Docker Desktop runs PostgreSQL and Redis. Python runs natively in a venv.

## TECH STACK (fixed — do not substitute)

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x + Alembic, Pydantic v2
- LLM: `anthropic` SDK, model `claude-sonnet-4-6`, vision input, temperature 0
- Jobs: Celery + Redis (on Windows dev, run Celery with `--pool=solo`)
- DB: PostgreSQL 16 (via docker-compose); SQLite acceptable only for unit tests
- PDF/Image: pdf2image (Poppler on PATH), Pillow, opencv-python-headless
- Excel: openpyxl
- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind, axios,
  @tanstack/react-query, zustand, react-dropzone
- Auth: JWT (python-jose), bcrypt via passlib — single "lecturer" role for v1
- Storage: local `./storage` folder behind a `StorageService` interface (S3 later)

## REPOSITORY LAYOUT

```
exam-marker/
├── PROJECT_SPEC.md
├── .cursorrules
├── docker-compose.yml            # postgres:16 + redis:7 only (dev services)
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory, CORS, routers
│   │   ├── config.py             # pydantic-settings, reads .env
│   │   ├── database.py           # engine, session, Base
│   │   ├── models.py             # SQLAlchemy tables
│   │   ├── schemas.py            # Pydantic models incl. MarkingReport
│   │   ├── storage.py            # StorageService (local impl)
│   │   ├── marking/
│   │   │   ├── prompt_v3.md      # the marking system prompt (provided by me)
│   │   │   ├── prompt.py         # loads prompt, injects scheme/course placeholders
│   │   │   ├── preprocess.py     # pdf→images, deskew, contrast, auto-rotate
│   │   │   └── engine.py         # Claude call, JSON extraction, Pydantic validation, retries
│   │   ├── export/excel.py       # batch → .xlsx (3 sheets)
│   │   ├── worker.py             # Celery app + tasks: mark_script, mark_batch
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── courses.py        # course + marking-scheme CRUD
│   │       ├── batches.py        # create batch, upload scripts, progress, excel export
│   │       ├── scripts.py        # script detail, page images, report JSON
│   │       ├── review.py         # overrides (append-only), audit log
│   │       └── appeals.py        # REMARK mode
│   ├── tests/
│   ├── migrations/               # alembic
│   ├── requirements.txt
│   └── .env                      # NEVER committed
└── frontend/                     # Next.js app
```

## DATABASE MODEL (create in Phase 2, do not redesign later without asking)

- **users**(id, email, password_hash, name, created_at)
- **courses**(id, user_id FK, code, title, total_marks, grading_scale JSON,
  language, created_at)
- **marking_schemes**(id, course_id FK, version INT, content TEXT,
  special_instructions TEXT, selection_rule TEXT, created_at) — append-only versions
- **batches**(id, course_id FK, scheme_id FK, name, status
  [pending|processing|completed|failed], created_at)
- **scripts**(id, batch_id FK, original_filename, storage_key, page_count,
  student_name, matric_number, status [queued|processing|marked|failed|needs_review],
  total_awarded NUMERIC, percentage NUMERIC, grade TEXT, needs_human_review BOOL,
  model_version TEXT, prompt_version TEXT, created_at)
- **script_pages**(id, script_id FK, page_number, image_storage_key)
- **marking_reports**(id, script_id FK, report_json JSONB, transcription TEXT,
  human_readable TEXT, created_at) — append-only; re-marks add rows
- **overrides**(id, script_id FK, user_id FK, question TEXT, old_score NUMERIC,
  new_score NUMERIC, reason TEXT, created_at) — append-only, never update/delete
- **appeals**(id, script_id FK, questions JSON, appeal_note TEXT,
  result_report_id FK nullable, status, created_at)
- **audit_log**(id, user_id, entity, entity_id, action, detail JSON, created_at)

Rule: marking data is immutable. Corrections are new rows (overrides, new
marking_reports), never UPDATEs to existing marking rows.

## THE MARKING ENGINE (heart of the system)

1. `preprocess.py`: PDF → 300-DPI PNGs via pdf2image; per page: auto-rotate via OpenCV
   (detect orientation), deskew, contrast enhancement (CLAHE), downscale so the longest
   side ≤ 1568 px before sending to the API. Save processed images to storage and
   `script_pages`.
2. `prompt.py`: load `prompt_v3.md`; replace {{PLACEHOLDERS}} with course, scheme,
   selection rule, special instructions, MODE (MARK or REMARK), REVIEW_THRESHOLD=3.
3. `engine.py`:
   - Build a single messages call: system = injected prompt; user content = list of
     image blocks (base64, in page order) + a short text block "Mark this script."
   - temperature 0, max_tokens generous (16k).
   - Extract Part A JSON (find first `{` after "Part A" or first fenced json block),
     strip fences, parse, validate against the `MarkingReport` Pydantic schema.
   - On JSON validation failure: retry once with an appended corrective instruction;
     if it fails again, mark script status=failed with the raw output stored.
   - Store report_json, human_readable (Part B), transcription; set script fields
     (total, %, grade, needs_human_review) from validated JSON.
   - Enforce server-side sanity checks independently of the model: per-question
     awarded ≤ max, totals recomputed in Python (trust our arithmetic, not the
     model's), percentage recomputed.
4. `worker.py`: `mark_batch` fans out `mark_script` tasks (one API call per script,
   never multiple scripts per call). Update batch status when all done. Retries: 2
   with exponential backoff on API/transient errors.

## EXCEL EXPORT (`export/excel.py`)

Workbook per batch:
- Sheet "Summary": Name | Matric | Q1..Qn | Total | % | Grade | Needs Review | Overridden
- Sheet "Flags": every low-confidence/anomaly item: matric, page, question, detail, impact
- Sheet "Item Analysis": per question: average, max, min, % attempted, % scoring ≥50%

## API ENDPOINTS (Phase 2–3)

- POST /auth/register, POST /auth/login
- CRUD /courses, POST /courses/{id}/schemes (new version)
- POST /batches (course_id, scheme_id, name)
- POST /batches/{id}/scripts (multipart, multiple PDFs) → creates scripts, queues jobs
- POST /batches/{id}/start → enqueue mark_batch
- GET /batches/{id} → status + per-script progress
- GET /batches/{id}/export.xlsx
- GET /scripts/{id} → detail incl. latest report JSON
- GET /scripts/{id}/pages/{n}.png
- POST /scripts/{id}/overrides
- POST /scripts/{id}/appeals → runs REMARK mode on cited questions only
- GET /scripts/{id}/history → all reports + overrides + appeals (audit view)

## FRONTEND PAGES (Phase 4)

- /login
- /courses (list/create), /courses/[id] (schemes, batches)
- /batches/[id] — dashboard: upload dropzone, start button, live progress
  (react-query polling every 3 s), per-script table with status chips,
  "Export Excel" button, filter "needs review"
- /scripts/[id] — REVIEW SCREEN: left = page images with zoom + page nav;
  right = per-question accordion showing mark points (decision, marks, evidence
  quote), strengths/missing/errors, override button (score + reason), appeal
  button (question + note), history tab
- Clean, dense, professional UI; loading and error states everywhere.

## BUILD PHASES (work strictly in this order)

- **Phase 1 — CLI core:** preprocess + prompt + engine + excel as a CLI:
  `python -m app.cli mark --pdf x.pdf --scheme scheme.txt --course "..." --out report.json`
  No DB, no web. Includes unit tests with a fake Anthropic client.
- **Phase 2 — API + DB:** FastAPI app, models, Alembic migration, auth, course/scheme/
  batch/script endpoints, storage service. Marking still callable synchronously
  behind a flag for testing.
- **Phase 3 — Workers:** Celery + Redis, mark_batch/mark_script tasks, progress
  reporting, Excel export endpoint.
- **Phase 4 — Frontend:** all pages above against the real API.
- **Phase 5 — Review/appeals/audit:** overrides, appeals (REMARK), history endpoints
  + UI.
- **Phase 6 — Hardening:** docker-compose for full stack, rate limiting, input
  validation pass, backup notes, README.

## CURSOR RULES (copy into `.cursorrules`)

```
You are building ExamMarker per PROJECT_SPEC.md. Always read it before major work.

Environment: Windows 10, PowerShell. Give PowerShell commands (venv\Scripts\activate,
not source). Celery dev commands must use --pool=solo. Poppler is installed and on PATH.

Principles:
1. Small steps. Implement exactly what is asked for the current phase; do not build
   ahead. After each task, tell me exactly how to run and test it.
2. Never invent API behavior. The Anthropic call signature and marking JSON schema are
   defined in PROJECT_SPEC.md and prompt_v3.md; if unsure, ask.
3. Marking data is immutable — corrections are appended rows, never UPDATEs.
4. All money-grade arithmetic (totals, percentages) is recomputed in Python; never
   trust model arithmetic.
5. Secrets only in .env (gitignored). Never print or commit ANTHROPIC_API_KEY.
6. Every new module gets at least one pytest test; external APIs are faked in tests.
7. Type hints everywhere; Pydantic v2 models for all request/response bodies.
8. If a library approach fails twice, stop and propose an alternative instead of
   thrashing.
9. When you finish a task, output: files changed, how to test, and a one-line
   conventional commit message.
```

## DEFINITION OF DONE (v1)

A lecturer can: log in → create a course + paste marking scheme → create a batch →
drag in 50 scanned PDFs → click Start → watch progress → open any script and see the
scan beside the per-mark-point breakdown → override a score with a reason → file an
appeal that re-marks one question → download an Excel summary. Every score is traceable
to scheme point + student's words, and nothing marking-related is ever deleted.
