import { useParams } from '@tanstack/react-router'
import { useDevisDetail, useDevisVersions } from '@/api/queries/useDevis'
import { DevisVersionsTab } from './components/DevisVersionsTab'

export default function DevisVersionsPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const devisId = parseInt(id, 10)

  const { data: devis, isLoading } = useDevisDetail(devisId)
  const { data: versions = [], isLoading: versionsLoading } = useDevisVersions(devisId)

  if (isLoading || versionsLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="h-3 skel rounded w-36" />
            <div className="h-2 skel rounded w-52" />
          </div>
        ))}
      </div>
    )
  }

  if (!devis) return null

  return <DevisVersionsTab devis={devis} versions={versions} />
}
