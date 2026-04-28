import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useCustomerDetail, useUpdateCustomer } from '@/api/queries/useCustomers'
import { normalizeError } from '@shared/errors/normalizer'
import { ArrowLeft, Save } from 'lucide-react'
import type { CustomerUpdate, CustomerType } from '@/types/customer'

const CUSTOMER_TYPE_LABELS: Record<CustomerType, string> = {
  individual: 'Particulier',
  company: 'Entreprise',
  professional: 'Professionnel',
  association: 'Association',
}

const CUSTOMER_TYPES: CustomerType[] = ['individual', 'company', 'professional', 'association']

export default function CustomerEditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const customerId = Number(id)

  const { data: customer, isLoading, error: loadError } = useCustomerDetail(customerId)
  const updateMutation = useUpdateCustomer()

  const [customerType, setCustomerType] = useState<CustomerType>('individual')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [country, setCountry] = useState('France')
  const [notes, setNotes] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!customer) return
    setCustomerType(customer.customer_type ?? 'individual')
    setFirstName(customer.first_name ?? '')
    setLastName(customer.last_name ?? '')
    setCompanyName(customer.company_name ?? '')
    setEmail(customer.email ?? '')
    setPhone(customer.phone ?? '')
    setAddress(customer.address ?? '')
    setCity(customer.city ?? '')
    setPostalCode(customer.postal_code ?? '')
    setCountry(customer.country ?? 'France')
    setNotes(customer.notes ?? '')
  }, [customer])

  const isCompanyType = customerType !== 'individual'

  const handleSave = async () => {
    setSaveError(null)
    setSaved(false)
    try {
      const payload: CustomerUpdate = {
        customer_type: customerType,
        email: email || undefined,
        phone: phone || undefined,
        first_name: isCompanyType ? undefined : firstName || undefined,
        last_name: isCompanyType ? undefined : lastName || undefined,
        company_name: isCompanyType ? companyName || undefined : undefined,
        address: address || undefined,
        city: city || undefined,
        postal_code: postalCode || undefined,
        country: country || undefined,
        notes: notes || undefined,
      }
      await updateMutation.mutateAsync({ id: customerId, data: payload })
      setSaved(true)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la sauvegarde')
    }
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4">
        <div className="h-8 w-44 skel rounded animate-pulse" />
        <div className="card p-6 space-y-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (loadError || !customer) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto">
        <div className="card p-8 text-center text-danger">
          {loadError ? normalizeError(loadError).message : 'Client introuvable'}
        </div>
      </div>
    )
  }

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          to="/customers/$id"
          params={{ id: String(customerId) }}
          className="btn-secondary btn-sm flex items-center gap-2 min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </Link>
        <div className="flex-1 min-w-0">
          <PageHeader title="Modifier le client" subtitle={`${customer.first_name || customer.company_name} ${customer.last_name ?? ''}`} />
        </div>
      </div>

      {/* Identité */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Identité
        </h2>

        {/* Type */}
        <div>
          <label className="text-sm text-dark-400 mb-1.5 block">Type de client</label>
          <select
            className="input w-full"
            value={customerType}
            onChange={e => setCustomerType(e.target.value as CustomerType)}
          >
            {CUSTOMER_TYPES.map(t => (
              <option key={t} value={t}>
                {CUSTOMER_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </div>

        {/* Particulier : prénom + nom */}
        {!isCompanyType && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-dark-400 mb-1.5 block">Prénom</label>
              <input
                className="input w-full"
                placeholder="Prénom"
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm text-dark-400 mb-1.5 block">Nom</label>
              <input
                className="input w-full"
                placeholder="Nom"
                value={lastName}
                onChange={e => setLastName(e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Entreprise / Pro / Association : raison sociale */}
        {isCompanyType && (
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Raison sociale</label>
            <input
              className="input w-full"
              placeholder="Nom de l'entreprise"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
            />
          </div>
        )}

        {/* Email + Téléphone */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Email</label>
            <input
              type="email"
              className="input w-full"
              placeholder="email@exemple.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Téléphone</label>
            <input
              type="tel"
              className="input w-full"
              placeholder="+33 6 00 00 00 00"
              value={phone}
              onChange={e => setPhone(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Adresse */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Adresse
        </h2>
        <div>
          <label className="text-sm text-dark-400 mb-1.5 block">Rue</label>
          <input
            className="input w-full"
            placeholder="12 rue de la Paix"
            value={address}
            onChange={e => setAddress(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-[1fr_7rem] gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Ville</label>
            <input
              className="input w-full"
              placeholder="Paris"
              value={city}
              onChange={e => setCity(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Code postal</label>
            <input
              className="input w-full"
              placeholder="75001"
              value={postalCode}
              onChange={e => setPostalCode(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="text-sm text-dark-400 mb-1.5 block">Pays</label>
          <input
            className="input w-full"
            placeholder="France"
            value={country}
            onChange={e => setCountry(e.target.value)}
          />
        </div>
      </div>

      {/* Notes */}
      <div className="card p-6">
        <label className="text-sm text-dark-400 mb-1.5 block">Notes internes</label>
        <textarea
          className="input w-full min-h-[80px] resize-none"
          placeholder="Notes…"
          value={notes}
          onChange={e => setNotes(e.target.value)}
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4 justify-end flex-wrap">
        {saveError != null && (
          <p className="text-sm text-danger">{saveError}</p>
        )}
        {saved && (
          <p className="text-sm text-green-400">Sauvegardé ✓</p>
        )}
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="btn-primary flex items-center gap-2 min-h-[44px]"
        >
          {updateMutation.isPending ? (
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Enregistrer
        </button>
      </div>
    </div>
  )
}
