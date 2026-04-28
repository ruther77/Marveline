import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import { AlertTriangle, ArrowLeft } from 'lucide-react'

export default function DepartureBlockedPage() {
  return (
    <div className="p-4 md:p-6 max-w-2xl lg:max-w-5xl mx-auto text-center space-y-4">
      <AlertTriangle size={48} className="mx-auto text-red-400" />
      <PageHeader title="Départ bloqué" subtitle="Ce départ ne peut pas être effectué. Vérifiez les pré-checks et les risques." />
      <Link to="/operations" className="inline-flex items-center gap-2 text-sm text-primary-400 hover:text-primary-300">
        <ArrowLeft size={14} /> Retour aux opérations
      </Link>
    </div>
  )
}
