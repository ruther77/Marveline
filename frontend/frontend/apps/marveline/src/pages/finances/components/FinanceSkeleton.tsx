const SKEL = 'bg-dark-700/60 rounded-lg'
const CARD = 'rounded-2xl border border-dark-700/50 bg-gradient-to-br from-dark-800/80 to-dark-900/90 shadow-lg shadow-black/10'

export function FinancePageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className={`${CARD} p-5 flex items-start gap-4`}>
            <div className={`w-12 h-12 rounded-xl ${SKEL}`} />
            <div className="flex-1 space-y-2.5">
              <div className={`h-2.5 w-16 ${SKEL}`} />
              <div className={`h-7 w-24 ${SKEL}`} />
              <div className={`h-4 w-20 rounded-md ${SKEL}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[1, 2].map((i) => (
          <div key={i} className={`${CARD} p-6 space-y-4`}>
            <div className="space-y-1.5">
              <div className={`h-3.5 w-28 ${SKEL}`} />
              <div className={`h-2.5 w-16 ${SKEL}`} />
            </div>
            <div className={`h-52 ${SKEL}`} />
          </div>
        ))}
      </div>

      {/* Table */}
      <div className={CARD}>
        <div className="px-6 py-4">
          <div className={`h-3.5 w-36 ${SKEL}`} />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="px-6 py-3.5 flex items-center gap-6 border-t border-dark-700/20"
          >
            <div className={`h-3 w-10 ${SKEL}`} />
            <div className={`h-3 flex-1 ${SKEL}`} />
            <div className={`h-3 w-20 ${SKEL}`} />
            <div className={`h-3 w-14 ${SKEL}`} />
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
        <div key={i} className={`${CARD} p-5 flex items-start gap-4`}>
          <div className={`w-12 h-12 rounded-xl ${SKEL}`} />
          <div className="flex-1 space-y-2.5">
            <div className={`h-2.5 w-16 ${SKEL}`} />
            <div className={`h-7 w-24 ${SKEL}`} />
          </div>
        </div>
      ))}
    </div>
  )
}
