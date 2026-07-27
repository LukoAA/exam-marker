"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ScriptUploader } from "@/components/script-uploader";
import { StatusChip } from "@/components/status-chip";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { api } from "@/lib/api";
import type { BatchDetail } from "@/lib/types";

export default function BatchDetailPage() {
  const { ready } = useRequireAuth();
  const { id: batchId } = useParams<{ id: string }>();

  const batchQuery = useQuery({
    queryKey: ["batch", batchId],
    queryFn: async () => (await api.get<BatchDetail>(`/batches/${batchId}`)).data,
    enabled: ready,
    refetchInterval: 5000,
  });

  if (!ready) return null;

  const batch = batchQuery.data;

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
      {batchQuery.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
      {batchQuery.isError && <p className="text-sm text-red-600">Could not load batch.</p>}

      {batch && (
        <div className="mb-8 flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-semibold text-zinc-900">{batch.name}</h1>
          <StatusChip status={batch.status} kind="batch" />
        </div>
      )}

      <h2 className="mb-3 text-lg font-semibold text-zinc-900">Upload scripts</h2>
      <ScriptUploader batchId={batchId} />

      <h2 className="mb-3 text-lg font-semibold text-zinc-900">Scripts</h2>

      {batch && batch.scripts.length === 0 && (
        <p className="text-sm text-zinc-500">No scripts uploaded yet.</p>
      )}

      {batch && batch.scripts.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                <th className="px-4 py-3 font-medium">Filename</th>
                <th className="px-4 py-3 font-medium">Pages</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {batch.scripts.map((script) => (
                <tr
                  key={script.id}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/scripts/${script.id}`}
                      className="text-zinc-900 underline-offset-2 hover:underline"
                    >
                      {script.original_filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">{script.page_count ?? "—"}</td>
                  <td className="px-4 py-3">
                    <StatusChip status={script.status} kind="script" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
