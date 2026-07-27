const SCRIPT_STATUS_STYLES: Record<string, string> = {
  queued: "bg-zinc-100 text-zinc-700",
  processing: "bg-blue-100 text-blue-700",
  marked: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  needs_review: "bg-amber-100 text-amber-700",
};

const BATCH_STATUS_STYLES: Record<string, string> = {
  pending: "bg-zinc-100 text-zinc-700",
  processing: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function StatusChip({ status, kind }: { status: string; kind: "script" | "batch" }) {
  const styles = kind === "script" ? SCRIPT_STATUS_STYLES : BATCH_STATUS_STYLES;
  const className = styles[status] ?? "bg-zinc-100 text-zinc-700";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${className}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
