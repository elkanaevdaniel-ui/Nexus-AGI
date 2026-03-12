export default function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-64 mb-2" />
      <div className="h-4 bg-gray-100 rounded w-40 mb-8" />

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="h-3 bg-gray-100 rounded w-16 mb-2" />
            <div className="h-6 bg-gray-200 rounded w-12" />
          </div>
        ))}
      </div>

      {/* Content area */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="h-4 bg-gray-200 rounded w-32 mb-4" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-3 bg-gray-100 rounded w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
