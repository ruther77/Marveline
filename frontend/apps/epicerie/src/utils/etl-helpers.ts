// Helpers partagés ETL — formatters et constantes

export function formatCents(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return (value / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const STATUT_LABELS: Record<string, string> = {
  PENDING: 'En attente',
  RUNNING: 'Traitement…',
  PREVIEW: 'À valider',
  VALIDATED: 'Validée',
  REJECTED: 'Rejetée',
  SUCCES: 'Succès',
  PARTIEL: 'Partiel',
  ECHEC: 'Échec',
  REVERTED: 'Annulée',
}

export const STATUT_COLORS: Record<string, string> = {
  PENDING: 'bg-slate-100 text-slate-500',
  RUNNING: 'bg-emerald-50 text-emerald-600',
  PREVIEW: 'bg-amber-50 text-amber-600',
  VALIDATED: 'bg-green-50 text-green-600',
  REJECTED: 'bg-red-50 text-red-600',
  SUCCES: 'bg-green-50 text-green-600',
  PARTIEL: 'bg-amber-50 text-amber-600',
  ECHEC: 'bg-red-50 text-red-600',
  REVERTED: 'bg-orange-50 text-orange-600',
}
