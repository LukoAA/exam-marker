const DECISION_STYLES: Record<string, string> = {
  AWARDED: "bg-green-100 text-green-700",
  PARTIAL: "bg-amber-100 text-amber-700",
  "NOT AWARDED": "bg-red-100 text-red-700",
};

export function DecisionBadge({ decision }: { decision: string }) {
  const className = DECISION_STYLES[decision] ?? "bg-zinc-100 text-zinc-700";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {decision}
    </span>
  );
}
