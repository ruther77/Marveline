import { useState, useEffect } from 'react'
import { useFeatureFlags, useToggleFeatureFlag, useTenantSettings, useUpdateTenantSettings } from '@/api/queries'
import { ActionError } from '@shared/components/ui/ActionError'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'
import { PageHeader } from '@shared/components/ui/Breadcrumb'
import {
  Settings,
  Mail,
  Palette,
  ToggleLeft,
  ToggleRight,
  Building2,
  Shield,
  Loader2,
  Save,
  Euro,
} from 'lucide-react'

export default function AdminSettingsPage() {
  const { data: flagsData, isLoading: flagsLoading } = useFeatureFlags()
  const flags = flagsData?.items ?? []
  const toggleFlag = useToggleFeatureFlag()

  const { data: settings, isLoading: settingsLoading, error: settingsError, refetch: refetchSettings } = useTenantSettings()
  const updateSettings = useUpdateTenantSettings()

  const [form, setForm] = useState({
    company_name: '',
    company_email: '',
    company_phone: '',
    company_address: '',
    origin_postal_code: '',
    vat_rate: 0.20,
    hourly_rate_weekday: 30,
    hourly_rate_weekend: 60,
    deposit_rate: 0.30,
    default_currency: 'EUR',
  })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (settings) {
      setForm({
        company_name: settings.company_name ?? '',
        company_email: settings.company_email ?? '',
        company_phone: settings.company_phone ?? '',
        company_address: settings.company_address ?? '',
        origin_postal_code: settings.origin_postal_code ?? '',
        vat_rate: settings.vat_rate,
        hourly_rate_weekday: settings.hourly_rate_weekday,
        hourly_rate_weekend: settings.hourly_rate_weekend,
        deposit_rate: settings.deposit_rate,
        default_currency: settings.default_currency,
      })
    }
  }, [settings])

  function handleSave() {
    updateSettings.mutate(
      {
        company_name: form.company_name || null,
        company_email: form.company_email || null,
        company_phone: form.company_phone || null,
        company_address: form.company_address || null,
        origin_postal_code: form.origin_postal_code || null,
        vat_rate: form.vat_rate,
        hourly_rate_weekday: form.hourly_rate_weekday,
        hourly_rate_weekend: form.hourly_rate_weekend,
        deposit_rate: form.deposit_rate,
        default_currency: form.default_currency,
      },
      {
        onSuccess: () => {
          setSaved(true)
          setTimeout(() => setSaved(false), 2000)
        },
      }
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Paramètres système" subtitle="Configuration globale de la plateforme" />

      {/* Tenant info — éditable */}
      <section className="card overflow-hidden p-0">
        <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2">
          <Building2 className="w-4 h-4 text-primary-400" />
          <h2 className="text-sm font-semibold">Informations & paramètres métier</h2>
        </div>
        {settingsError ? (
          <div className="p-4">
            <ErrorState onRetry={() => refetchSettings()} />
          </div>
        ) : settingsLoading ? (
          <div className="p-4 space-y-4 animate-pulse">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="h-3 skel rounded w-32" />
                  <div className="h-9 skel rounded" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Coordonnées */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Nom de l'organisation</label>
                <input
                  type="text"
                  value={form.company_name}
                  onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))}
                  className="input"
                  placeholder="Ma Société"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">E-mail de contact</label>
                <input
                  type="email"
                  value={form.company_email}
                  onChange={e => setForm(f => ({ ...f, company_email: e.target.value }))}
                  className="input"
                  placeholder="contact@masociete.fr"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Téléphone</label>
                <input
                  type="text"
                  value={form.company_phone}
                  onChange={e => setForm(f => ({ ...f, company_phone: e.target.value }))}
                  className="input"
                  placeholder="+33 1 23 45 67 89"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Adresse</label>
                <input
                  type="text"
                  value={form.company_address}
                  onChange={e => setForm(f => ({ ...f, company_address: e.target.value }))}
                  className="input"
                  placeholder="1 rue de la Paix, Paris"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Code postal entrepôt</label>
                <input
                  type="text"
                  value={form.origin_postal_code}
                  onChange={e => setForm(f => ({ ...f, origin_postal_code: e.target.value }))}
                  className="input"
                  placeholder="60000"
                  maxLength={10}
                />
                <p className="text-xs text-dark-500 mt-1">Utilisé comme origine pour les devis transporteurs (Boxtal)</p>
              </div>
            </div>

            {/* Paramètres financiers */}
            <div>
              <h3 className="flex items-center gap-2 text-xs font-semibold text-dark-500 uppercase tracking-wider mb-4">
                <Euro className="w-3.5 h-3.5" /> Paramètres financiers
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-400 mb-1">TVA (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={form.vat_rate}
                    onChange={e => setForm(f => ({ ...f, vat_rate: parseFloat(e.target.value) || 0 }))}
                    className="input"
                  />
                  <p className="text-xs text-dark-400 mt-1">{(form.vat_rate * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Taux acompte (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={form.deposit_rate}
                    onChange={e => setForm(f => ({ ...f, deposit_rate: parseFloat(e.target.value) || 0 }))}
                    className="input"
                  />
                  <p className="text-xs text-dark-400 mt-1">{(form.deposit_rate * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Taux horaire semaine (€/h)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    value={form.hourly_rate_weekday}
                    onChange={e => setForm(f => ({ ...f, hourly_rate_weekday: parseFloat(e.target.value) || 0 }))}
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Taux horaire weekend (€/h)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    value={form.hourly_rate_weekend}
                    onChange={e => setForm(f => ({ ...f, hourly_rate_weekend: parseFloat(e.target.value) || 0 }))}
                    className="input"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-4 pt-2 border-t border-dark-600">
              {saved && (
                <span className="text-xs text-success font-medium">Enregistré ✓</span>
              )}
              <ActionError
                message={updateSettings.isError ? (normalizeError(updateSettings.error).message || 'Erreur de sauvegarde') : null}
                onDismiss={() => updateSettings.reset()}
              />
              <button
                onClick={handleSave}
                disabled={updateSettings.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {updateSettings.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Enregistrer
              </button>
            </div>
          </div>
        )}
      </section>

      {/* SMTP — placeholder */}
      <section className="card overflow-hidden p-0">
        <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2">
          <Mail className="w-4 h-4 text-info" />
          <h2 className="text-sm font-semibold">Configuration e-mail (SMTP)</h2>
          <span className="ml-auto text-xs bg-warning/10 text-warning px-2 py-0.5 rounded-lg">Lecture seule</span>
        </div>
        <div className="p-4">
          <p className="text-sm text-dark-500">
            La configuration SMTP est gérée via les variables d'environnement du serveur.
            Contactez votre administrateur système pour modifier ces valeurs.
          </p>
        </div>
      </section>

      {/* Branding — placeholder */}
      <section className="card overflow-hidden p-0">
        <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2">
          <Palette className="w-4 h-4 text-subtle" />
          <h2 className="text-sm font-semibold">Branding</h2>
          <span className="ml-auto text-xs bg-subtle/10 text-subtle px-2 py-0.5 rounded-lg">À venir</span>
        </div>
        <div className="p-4">
          <p className="text-sm text-dark-500">
            La personnalisation du logo, des couleurs et des modèles de documents sera disponible prochainement.
          </p>
        </div>
      </section>

      {/* Feature flags */}
      <section className="card overflow-hidden p-0">
        <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <h2 className="text-sm font-semibold">Fonctionnalités activées</h2>
        </div>
        <div className="p-4">
          {flagsLoading ? (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between py-4 border-b border-dark-600">
                  <div className="space-y-1.5">
                    <div className="h-3 skel rounded w-32" />
                    <div className="h-2 skel rounded w-48" />
                  </div>
                  <div className="w-10 h-5 skel rounded-full shrink-0" />
                </div>
              ))}
            </div>
          ) : flags.length === 0 ? (
            <p className="text-sm text-dark-400">Aucun feature flag configuré.</p>
          ) : (
            <div className="space-y-2">
              {flags.map((flag) => (
                <div key={flag.id} className="flex items-center justify-between py-4 border-b border-dark-600 last:border-0">
                  <div className="min-w-0 pr-4">
                    <p className="text-sm font-medium">{flag.name}</p>
                    {flag.description && (
                      <p className="text-xs text-dark-500 mt-0.5">{flag.description}</p>
                    )}
                  </div>
                  <button
                    onClick={() => toggleFlag.mutate({ id: flag.id, is_enabled: !flag.is_enabled })}
                    disabled={toggleFlag.isPending}
                    className="shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
                  >
                    {flag.is_enabled ? (
                      <ToggleRight className="w-8 h-8 text-primary-400" />
                    ) : (
                      <ToggleLeft className="w-8 h-8 text-dark-400" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Security info */}
      <section className="card overflow-hidden p-0">
        <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2">
          <Shield className="w-4 h-4 text-success" />
          <h2 className="text-sm font-semibold">Sécurité</h2>
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4">
          <div>
            <dt className="block text-sm text-dark-400 mb-1">Durée de session</dt>
            <dd className="text-sm mt-1">30 minutes (inactivité)</dd>
          </div>
          <div>
            <dt className="block text-sm text-dark-400 mb-1">Tentatives de connexion max</dt>
            <dd className="text-sm mt-1">5 / minute</dd>
          </div>
          <div>
            <dt className="block text-sm text-dark-400 mb-1">MFA obligatoire</dt>
            <dd className="text-sm mt-1">Non (recommandé pour les admins)</dd>
          </div>
          <div>
            <dt className="block text-sm text-dark-400 mb-1">Isolation multi-tenant</dt>
            <dd className="text-sm text-success font-semibold mt-1">Activée</dd>
          </div>
        </dl>
      </section>
    </div>
  )
}
