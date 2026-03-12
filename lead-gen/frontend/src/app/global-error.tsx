"use client";

export function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="antialiased flex items-center justify-center min-h-screen bg-[#f9fafb]">
        <div className="text-center max-w-md p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Something went wrong
          </h2>
          <p className="text-gray-500 mb-6 text-sm">
            {error.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={reset}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
