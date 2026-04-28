import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Bell, Mail, Smartphone } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'

interface NotifCategory {
  id: string
  label: string
  description: string
}

const NOTIF_CATEGORIES: NotifCategory[] = [
  { id: 'reservation_created', label: 'Nouvelles réservations', description: 'Quand une réservation est créée ou modifiée' },
  { id: 'invoice_paid', label: 'Paiements reçus', description: 'Quand une facture est payée' },
  { id: 'invoice_overdue', label: 'Factures en retard', description: 'Rappels de paiement en attente' },
  { id: 'low_stock', label: 'Stock faible', description: "Quand le stock d'un article passe sous le seuil" },
  { id: 'return_late', label: 'Retours en retard', description: 'Matériel non retourné à la date prévue' },
  { id: 'deposit_missing', label: 'Acomptes manquants', description: 'Réservations confirmées sans acompte' },
]

type Channel = 'inapp' | 'email'

function useNotifPrefs() {
  const STORAGE_KEY = 'notif_prefs_v1'

  const loadPrefs = (): Record<string, Record<Channel, boolean>> => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) return JSON.parse(raw)
    } catch { /* ignore */ }
    const defaults: Record<string, Record<Channel, boolean>> = {}
    NOTIF_CATEGORIES.forEach(c => {
      defaults[c.id] = { inapp: true, email: false }
    })
    return defaults
  }

  const [prefs, setPrefs] = useState(loadPrefs)
  const [saved, setSaved] = useState(false)

  const toggle = (categoryId: string, channel: Channel) => {
    setPrefs(prev => ({
      ...prev,
      [categoryId]: { ...prev[categoryId], [channel]: !prev[categoryId][channel] },
    }))
    setSaved(false)
  }

  const save = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
    setSaved(true)
  }

  return { prefs, toggle, save, saved }
}

export default function NotificationsSettingsPage() {
  const { prefs, toggle, save, saved } = useNotifPrefs()

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <BackButton label="Retour" />
        <div className="flex-1 min-w-0">
          <PageHeader title="Paramètres des notifications" subtitle="Choisissez comment et quand vous êtes notifié" />
        </div>
      </div>

      {/* Légende canaux */}
      <div className="card p-4">
        <div className="flex items-center gap-6 text-sm text-dark-400">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4" />
            In-app
          </div>
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4" />
            Email
          </div>
          <div className="flex items-center gap-2 text-dark-600">
            <Smartphone className="w-4 h-4" />
            Push (bientôt)
          </div>
        </div>
      </div>

      {/* Catégories */}
      <div className="card divide-y divide-dark-600">
        {NOTIF_CATEGORIES.map(cat => (
          <div key={cat.id} className="flex items-center justify-between p-4 gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-dark-100">{cat.label}</p>
              <p className="text-xs text-dark-500 mt-0.5">{cat.description}</p>
            </div>
            <div className="flex items-center gap-4 shrink-0">
              {/* In-app toggle */}
              <button
                onClick={() => toggle(cat.id, 'inapp')}
                aria-label={`Notifications in-app : ${cat.label}`}
                className={[
                  'relative w-10 h-6 rounded-full transition-colors min-h-[44px] flex items-center',
                  prefs[cat.id]?.inapp ? 'bg-primary-500' : 'bg-dark-600',
                ].join(' ')}
              >
                <span
                  className={[
                    'absolute w-4 h-4 rounded-full bg-white shadow transition-transform',
                    prefs[cat.id]?.inapp ? 'translate-x-5' : 'translate-x-1',
                  ].join(' ')}
                />
              </button>
              {/* Email toggle */}
              <button
                onClick={() => toggle(cat.id, 'email')}
                aria-label={`Notifications email : ${cat.label}`}
                className={[
                  'relative w-10 h-6 rounded-full transition-colors min-h-[44px] flex items-center',
                  prefs[cat.id]?.email ? 'bg-primary-500' : 'bg-dark-600',
                ].join(' ')}
              >
                <span
                  className={[
                    'absolute w-4 h-4 rounded-full bg-white shadow transition-transform',
                    prefs[cat.id]?.email ? 'translate-x-5' : 'translate-x-1',
                  ].join(' ')}
                />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Save */}
      <div className="flex items-center justify-end gap-4">
        {saved && (
          <p className="text-sm text-green-400">Préférences sauvegardées ✓</p>
        )}
        <button
          onClick={save}
          className="btn-primary min-h-[44px] px-6"
        >
          Enregistrer
        </button>
      </div>
    </div>
  )
}
