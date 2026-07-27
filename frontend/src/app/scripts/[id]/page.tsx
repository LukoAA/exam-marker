"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DecisionBadge } from "@/components/decision-badge";
import { StatusChip } from "@/components/status-chip";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { usePageImage } from "@/hooks/use-page-image";
import { api } from "@/lib/api";
import type { MarkingReportJson, ReportQuestion, ScriptDetail } from "@/lib/types";

const ZOOM_STEP = 0.25;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;

export default function ScriptReviewPage() {
  const { ready } = useRequireAuth();
  const { id: scriptId } = useParams<{ id: string }>();

  const scriptQuery = useQuery({
    queryKey: ["script", scriptId],
    queryFn: async () => (await api.get<ScriptDetail>(`/scripts/${scriptId}`)).data,
    enabled: ready,
  });

  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1);

  const script = scriptQuery.data;
  const pageCount = script?.page_count ?? 0;
  const { url: pageImageUrl, loading: pageLoading, error: pageError } = usePageImage(
    scriptId,
    pageCount > 0 ? currentPage : null
  );

  if (!ready) return null;

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* LEFT: scanned page viewer */}
      <div className="flex w-1/2 flex-col border-r border-zinc-200 bg-zinc-50">
        <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm disabled:opacity-40"
            >
              ← Prev
            </button>
            <span className="text-sm text-zinc-600">
              Page {pageCount > 0 ? currentPage : "—"} of {pageCount || "—"}
            </span>
            <button
              type="button"
              disabled={currentPage >= pageCount}
              onClick={() => setCurrentPage((p) => Math.min(pageCount, p + 1))}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm disabled:opacity-40"
            >
              Next →
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - ZOOM_STEP))}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm"
            >
              −
            </button>
            <span className="w-12 text-center text-sm text-zinc-600">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + ZOOM_STEP))}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm"
            >
              Reset
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6">
          {pageCount === 0 && (
            <p className="text-sm text-zinc-500">No page images available for this script.</p>
          )}
          {pageLoading && <p className="text-sm text-zinc-500">Loading page…</p>}
          {pageError && <p className="text-sm text-red-600">Could not load this page image.</p>}
          {pageImageUrl && (
            // eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL, not a static asset
            <img
              src={pageImageUrl}
              alt={`Page ${currentPage}`}
              style={{ width: `${zoom * 100}%` }}
              className="mx-auto shadow-md"
            />
          )}
        </div>
      </div>

      {/* RIGHT: marking result */}
      <div className="w-1/2 overflow-y-auto p-6">
        {scriptQuery.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
        {scriptQuery.isError && <p className="text-sm text-red-600">Could not load script.</p>}

        {script && !script.latest_report && (
          <div className="rounded-lg border border-zinc-200 bg-white p-8 text-center shadow-sm">
            <p className="mb-3 text-sm font-medium text-zinc-700">Not yet marked</p>
            <StatusChip status={script.status} kind="script" />
            <p className="mt-4 text-sm text-zinc-500">
              This script hasn&apos;t been marked yet. Once marking runs, the breakdown will
              appear here.
            </p>
          </div>
        )}

        {script?.latest_report && (
          <ReportView filename={script.original_filename} report={script.latest_report.report_json} />
        )}
      </div>
    </div>
  );
}

function ReportView({
  filename,
  report,
}: {
  filename: string;
  report: MarkingReportJson;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{filename}</p>
        <h1 className="mt-1 text-xl font-semibold text-zinc-900">
          {report.student_name ?? "Unknown student"}
        </h1>
        <p className="text-sm text-zinc-600">
          {report.matric_number ?? "No matric number"} · {report.course_code}
        </p>

        <div className="mt-4 flex items-center gap-4">
          <span className="text-2xl font-semibold text-zinc-900">
            {report.total_awarded} / {report.total_possible}
          </span>
          <span className="text-sm text-zinc-600">{report.percentage}%</span>
          {report.grade && (
            <span className="rounded-full bg-zinc-900 px-3 py-1 text-sm font-medium text-white">
              {report.grade}
            </span>
          )}
        </div>

        {report.needs_human_review && (
          <div className="mt-4 rounded-md bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-800">Needs human review</p>
            {report.review_reasons.length > 0 && (
              <ul className="mt-1 list-inside list-disc text-sm text-amber-700">
                {report.review_reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4">
        {report.questions.map((question: ReportQuestion) => (
          <QuestionCard key={question.question} question={question} />
        ))}
      </div>

      {report.mcq_section.present && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-zinc-900">MCQ section</h3>
          <p className="text-sm text-zinc-600">Answers: {report.mcq_section.answer_string}</p>
          <p className="mt-1 text-sm text-zinc-600">
            Correct: {report.mcq_section.correct} · Wrong: {report.mcq_section.wrong} · Blank:{" "}
            {report.mcq_section.blank} · Ambiguous: {report.mcq_section.ambiguous} · Score:{" "}
            {report.mcq_section.score}
          </p>
        </div>
      )}

      {report.low_confidence_sections.length > 0 && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-zinc-900">Low-confidence sections</h3>
          <ul className="flex flex-col gap-1 text-sm text-zinc-600">
            {report.low_confidence_sections.map((s, i) => (
              <li key={i}>
                Page {s.page}, Q{s.question}: {s.text} — {s.impact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.page_anomalies.length > 0 && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-zinc-900">Page anomalies</h3>
          <ul className="flex flex-col gap-1 text-sm text-zinc-600">
            {report.page_anomalies.map((a, i) => (
              <li key={i}>
                Page {a.page} ({a.type}): {a.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-zinc-900">Overall feedback</h3>
        <dl className="flex flex-col gap-2 text-sm">
          <div>
            <dt className="font-medium text-zinc-700">Concepts understood</dt>
            <dd className="text-zinc-600">{report.overall_feedback.concepts_understood}</dd>
          </div>
          <div>
            <dt className="font-medium text-zinc-700">Weak areas</dt>
            <dd className="text-zinc-600">{report.overall_feedback.weak_areas}</dd>
          </div>
          <div>
            <dt className="font-medium text-zinc-700">Topics to revise</dt>
            <dd className="text-zinc-600">{report.overall_feedback.topics_to_revise}</dd>
          </div>
          <div>
            <dt className="font-medium text-zinc-700">Summary</dt>
            <dd className="text-zinc-600">{report.overall_feedback.summary}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

function QuestionCard({ question }: { question: ReportQuestion }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900">Question {question.question}</h3>
        <div className="flex items-center gap-2">
          {question.provisional && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              Provisional
            </span>
          )}
          <span className="text-sm font-medium text-zinc-700">
            {question.awarded} / {question.max_marks}
          </span>
        </div>
      </div>

      {!question.attempted && (
        <p className="mb-2 text-sm italic text-zinc-500">Not attempted</p>
      )}

      <div className="flex flex-col gap-2">
        {question.mark_points.map((point, i) => (
          <div key={i} className="rounded-md bg-zinc-50 p-3">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-sm text-zinc-700">{point.scheme_point}</span>
              <div className="flex shrink-0 items-center gap-2">
                <DecisionBadge decision={point.decision} />
                <span className="text-xs text-zinc-500">{point.marks} marks</span>
              </div>
            </div>
            <p className="text-sm italic text-zinc-600">&ldquo;{point.evidence}&rdquo;</p>
            {point.note && <p className="mt-1 text-xs text-zinc-500">{point.note}</p>}
          </div>
        ))}
      </div>

      {(question.strengths || question.missing_points || question.errors) && (
        <div className="mt-3 flex flex-col gap-1 text-xs text-zinc-600">
          {question.strengths && (
            <p>
              <span className="font-medium text-zinc-700">Strengths:</span> {question.strengths}
            </p>
          )}
          {question.missing_points && (
            <p>
              <span className="font-medium text-zinc-700">Missing:</span> {question.missing_points}
            </p>
          )}
          {question.errors && (
            <p>
              <span className="font-medium text-zinc-700">Errors:</span> {question.errors}
            </p>
          )}
        </div>
      )}

      {question.legibility_flags.length > 0 && (
        <p className="mt-2 text-xs text-amber-700">
          Legibility flags: {question.legibility_flags.join(", ")}
        </p>
      )}
    </div>
  );
}
