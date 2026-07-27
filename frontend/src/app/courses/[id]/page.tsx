"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useParams } from "next/navigation";
import { useState } from "react";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { api } from "@/lib/api";
import type { Course, MarkingScheme } from "@/lib/types";

export default function CourseDetailPage() {
  const { ready } = useRequireAuth();
  const { id: courseId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const courseQuery = useQuery({
    queryKey: ["course", courseId],
    queryFn: async () => (await api.get<Course>(`/courses/${courseId}`)).data,
    enabled: ready,
  });

  const schemesQuery = useQuery({
    queryKey: ["course", courseId, "schemes"],
    queryFn: async () => (await api.get<MarkingScheme[]>(`/courses/${courseId}/schemes`)).data,
    enabled: ready,
  });

  const [content, setContent] = useState("");
  const [selectionRule, setSelectionRule] = useState("");
  const [specialInstructions, setSpecialInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!ready) return null;

  async function handleAddScheme(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await api.post(`/courses/${courseId}/schemes`, {
        content,
        selection_rule: selectionRule || null,
        special_instructions: specialInstructions || null,
      });
      setContent("");
      setSelectionRule("");
      setSpecialInstructions("");
      await queryClient.invalidateQueries({ queryKey: ["course", courseId, "schemes"] });
    } catch (err) {
      if (isAxiosError(err) && err.response) {
        setError(err.response.data?.detail ?? "Could not add scheme version");
      } else {
        setError("Could not reach the server");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const course = courseQuery.data;
  const schemes = schemesQuery.data;

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      {courseQuery.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
      {courseQuery.isError && <p className="text-sm text-red-600">Could not load course.</p>}

      {course && (
        <div className="mb-8 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            {course.code}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-zinc-900">{course.title}</h1>
          <p className="mt-2 text-sm text-zinc-600">
            Total marks: {course.total_marks} · Language: {course.language}
          </p>
        </div>
      )}

      <h2 className="mb-3 text-lg font-semibold text-zinc-900">Marking scheme versions</h2>

      {schemesQuery.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
      {schemesQuery.isError && <p className="text-sm text-red-600">Could not load schemes.</p>}
      {schemes && schemes.length === 0 && (
        <p className="mb-6 text-sm text-zinc-500">No scheme versions yet — add one below.</p>
      )}

      <div className="mb-8 flex flex-col gap-3">
        {schemes?.map((scheme) => (
          <div key={scheme.id} className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
            <span className="text-sm font-semibold text-zinc-900">Version {scheme.version}</span>
            <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm text-zinc-700">
              {scheme.content}
            </pre>
            {scheme.selection_rule && (
              <p className="mt-2 text-xs text-zinc-500">Selection rule: {scheme.selection_rule}</p>
            )}
            {scheme.special_instructions && (
              <p className="mt-1 text-xs text-zinc-500">
                Special instructions: {scheme.special_instructions}
              </p>
            )}
          </div>
        ))}
      </div>

      <h2 className="mb-3 text-lg font-semibold text-zinc-900">Add a new scheme version</h2>
      <form
        onSubmit={handleAddScheme}
        className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="content" className="text-sm font-medium text-zinc-700">
            Marking scheme content
          </label>
          <textarea
            id="content"
            required
            rows={8}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={"Q1 (10 marks):\n  1a. Definition of X ........ 2 marks\n  ..."}
            className="rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="selection_rule" className="text-sm font-medium text-zinc-700">
            Selection rule (optional)
          </label>
          <input
            id="selection_rule"
            type="text"
            placeholder="e.g. Answer any 4 of 6 questions"
            value={selectionRule}
            onChange={(e) => setSelectionRule(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="special_instructions" className="text-sm font-medium text-zinc-700">
            Special instructions (optional)
          </label>
          <textarea
            id="special_instructions"
            rows={3}
            value={specialInstructions}
            onChange={(e) => setSpecialInstructions(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          {submitting ? "Adding…" : "Add scheme version"}
        </button>
      </form>
    </div>
  );
}
