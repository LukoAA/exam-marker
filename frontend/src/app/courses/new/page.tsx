"use client";

import { useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { api } from "@/lib/api";

export default function NewCoursePage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [totalMarks, setTotalMarks] = useState("");
  const [language, setLanguage] = useState("English");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!ready) return null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      // grading_scale is required by the API but not part of this form yet;
      // send an empty object (the marking prompt treats it as "not provided").
      await api.post("/courses", {
        code,
        title,
        total_marks: Number(totalMarks),
        language,
        grading_scale: {},
      });
      await queryClient.invalidateQueries({ queryKey: ["courses"] });
      router.push("/courses");
    } catch (err) {
      if (isAxiosError(err) && err.response) {
        setError(err.response.data?.detail ?? "Could not create course");
      } else {
        setError("Could not reach the server");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold text-zinc-900">New course</h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="code" className="text-sm font-medium text-zinc-700">
            Course code
          </label>
          <input
            id="code"
            type="text"
            required
            placeholder="CSC101"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="title" className="text-sm font-medium text-zinc-700">
            Title
          </label>
          <input
            id="title"
            type="text"
            required
            placeholder="Intro to Computing"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="total_marks" className="text-sm font-medium text-zinc-700">
            Total marks
          </label>
          <input
            id="total_marks"
            type="number"
            required
            min={1}
            step="0.5"
            value={totalMarks}
            onChange={(e) => setTotalMarks(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="language" className="text-sm font-medium text-zinc-700">
            Language of instruction
          </label>
          <input
            id="language"
            type="text"
            required
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create course"}
        </button>
      </form>
    </div>
  );
}
