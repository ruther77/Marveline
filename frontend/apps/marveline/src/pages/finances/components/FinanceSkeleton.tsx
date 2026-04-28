export function FinancePageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-5 flex items-start gap-4">
            <div className="w-11 h-11 rounded-xl bg-dark-700" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-16 bg-dark-700 rounded" />
              <div className="h-7 w-24 bg-dark-700 rounded" />
              <div className="h-3 w-20 bg-dark-700 rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5 space-y-3">
          <div className="h-4 w-32 bg-dark-700 rounded" />
          <div className="h-48 bg-dark-700 rounded" />
        </div>
        <div className="card p-5 space-y-3">
          <div className="h-4 w-32 bg-dark-700 rounded" />
          <div className="h-48 bg-dark-700 rounded" />
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-dark-700">
          <div className="h-4 w-40 bg-dark-700 rounded" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="px-5 py-3 flex items-center gap-4 border-b border-dark-700/30"
          >
            <div className="h-3 w-12 bg-dark-700 rounded" />
            <div className="h-3 w-24 bg-dark-700 rounded flex-1" />
            <div className="h-3 w-16 bg-dark-700 rounded" />
            <div className="h-3 w-12 bg-dark-700 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function FinanceKpiSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card p-5 flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl bg-dark-700" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-16 bg-dark-700 rounded" />
            <div className="h-7 w-24 bg-dark-700 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}
