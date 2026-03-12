function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-1/3 mb-4" />
      <div className="h-3 bg-gray-100 rounded w-2/3 mb-2" />
      <div className="h-3 bg-gray-100 rounded w-1/2" />
      <div className="flex gap-3 mt-6">
        <div className="h-8 bg-gray-100 rounded w-20" />
        <div className="h-8 bg-gray-100 rounded w-20" />
        <div className="h-8 bg-gray-100 rounded w-20" />
      </div>
    </div>
  );
}

export default function Loading() {
  return (
    <div>
      <div className="h-8 bg-gray-200 rounded w-48 mb-2 animate-pulse" />
      <div className="h-4 bg-gray-100 rounded w-72 mb-8 animate-pulse" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  );
}
