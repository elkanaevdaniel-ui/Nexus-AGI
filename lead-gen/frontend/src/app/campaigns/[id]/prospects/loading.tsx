export default function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-48 mb-6" />

      {/* Table skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="flex gap-4 p-4 border-b border-gray-100 bg-gray-50">
          {["w-32", "w-40", "w-24", "w-28", "w-20", "w-16"].map((w, i) => (
            <div key={i} className={`h-3 bg-gray-200 rounded ${w}`} />
          ))}
        </div>
        {/* Rows */}
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4 p-4 border-b border-gray-50">
            {["w-32", "w-40", "w-24", "w-28", "w-20", "w-16"].map((w, j) => (
              <div key={j} className={`h-3 bg-gray-100 rounded ${w}`} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
