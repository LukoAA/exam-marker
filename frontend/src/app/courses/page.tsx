"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { api } from "@/lib/api";
import type { Course } from "@/lib/types";

export default function CoursesPage() {
  const { ready } = useRequireAuth();

  const { data: courses, isLoading, isError } = useQuery({
    queryKey: ["courses"],
    queryFn: async () => (await api.get<Course[]>("/courses")).data,
    enabled: ready,
  });

  if (!ready) return null;

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-zinc-900">Courses</h1>
        <Link
          href="/courses/new"
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
        >
          New course
        </Link>
      </div>

      {isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
      {isError && <p className="text-sm text-red-600">Could not load courses.</p>}
      {courses && courses.length === 0 && (
        <p className="text-sm text-zinc-500">No courses yet. Create one to get started.</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {courses?.map((course) => (
          <Link
            key={course.id}
            href={`/courses/${course.id}`}
            className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm transition hover:border-zinc-300 hover:shadow"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              {course.code}
            </p>
            <h2 className="mt-1 text-lg font-semibold text-zinc-900">{course.title}</h2>
            <p className="mt-3 text-sm text-zinc-600">Total marks: {course.total_marks}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
