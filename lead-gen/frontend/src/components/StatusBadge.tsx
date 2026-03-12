interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-50 text-green-700 border-green-200",
  paused: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-blue-50 text-blue-700 border-blue-200",
  idle: "bg-gray-50 text-gray-600 border-gray-200",
  searching: "bg-blue-50 text-blue-700 border-blue-200",
  scoring: "bg-purple-50 text-purple-700 border-purple-200",
  enriching: "bg-amber-50 text-amber-700 border-amber-200",
  drafting: "bg-cyan-50 text-cyan-700 border-cyan-200",
  complete: "bg-green-50 text-green-700 border-green-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  new: "bg-gray-50 text-gray-600 border-gray-200",
  enriched: "bg-blue-50 text-blue-700 border-blue-200",
  scored: "bg-purple-50 text-purple-700 border-purple-200",
  contacted: "bg-amber-50 text-amber-700 border-amber-200",
  qualified: "bg-green-50 text-green-700 border-green-200",
  converted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lost: "bg-red-50 text-red-700 border-red-200",
  draft: "bg-gray-50 text-gray-600 border-gray-200",
  sent: "bg-blue-50 text-blue-700 border-blue-200",
  verified: "bg-green-50 text-green-700 border-green-200",
  guessed: "bg-amber-50 text-amber-700 border-amber-200",
};

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const colors = STATUS_COLORS[status] || "bg-gray-50 text-gray-600 border-gray-200";
  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span className={`inline-flex items-center rounded-full border font-medium capitalize ${colors} ${sizeClass}`}>
      {status}
    </span>
  );
}
