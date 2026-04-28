import { useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useBrand } from '@/brand/select'

// ── Carte de selection d'application ─────────────────────────────────────────

interface AppCardProps {
  logo: React.ReactNode
  name: string
  description: string
  accentColor: string
  onClick: () => void
}

function AppCard({ logo, name, description, accentColor, onClick }: AppCardProps) {
  return (
    <button
      onClick={onClick}
      className="group w-full max-w-xs flex flex-col items-center gap-5 rounded-2xl border border-[#d2d2d7] bg-white p-8 shadow-sm hover:shadow-md hover:border-[#a1a1a6] transition-all cursor-pointer text-left"
    >
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center"
        style={{ background: accentColor }}
      >
        {logo}
      </div>
      <div className="text-center">
        <p className="text-[17px] font-semibold text-[#1d1d1f] tracking-[-0.3px]">{name}</p>
        <p className="mt-1 text-[13px] text-[#6e6e73] leading-relaxed">{description}</p>
      </div>
      <span
        className="mt-auto text-[12px] font-semibold px-4 py-1.5 rounded-full text-white"
        style={{ background: accentColor }}
      >
        Acceder
      </span>
    </button>
  )
}

// ── Logos ──────────────────────────────────────────────────────────────────────

const MarvelineLogo = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 2h18v6H3zM3 10h18v6H3zM3 18h18v4H3z"/>
    <line x1="7" y1="2" x2="7" y2="20"/>
    <line x1="17" y1="2" x2="17" y2="20"/>
  </svg>
)

const SplendidLogo = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2l2.4 7.4H22l-6 4.4 2.3 7.2L12 16.6 5.7 21l2.3-7.2-6-4.4h7.6z"/>
  </svg>
)

const EpicerieLogo = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
    <line x1="3" y1="6" x2="21" y2="6"/>
    <path d="M16 10a4 4 0 0 1-8 0"/>
  </svg>
)

const RestaurantLogo = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 2v7c0 1.1.9 2 2 2h0V2"/>
    <path d="M7 2v20"/>
    <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3z"/>
  </svg>
)

// ── URLs des apps (env-overridable pour multi-domaine) ──────────────────────

const MASSACORP_BASE = import.meta.env.VITE_MASSACORP_URL || ''
const EPICERIE_URL = MASSACORP_BASE ? `${MASSACORP_BASE}/epicerie/` : '/epicerie/'
const RESTAURANT_URL = MASSACORP_BASE ? `${MASSACORP_BASE}/restaurant/` : '/restaurant/'
const SPLENDID_URL = (import.meta.env.VITE_SPLENDID_URL as string | undefined) || '/splendid/'

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AppSelectorPage() {
  const navigate = useNavigate()
  const marvelineAuth = useAuthStore()
  const brand = useBrand()

  function handleMarveline() {
    if (marvelineAuth.isAuthenticated) {
      navigate({ to: '/dashboard' as never })
    } else {
      navigate({ to: '/login' as never })
    }
  }

  function handleSplendid() {
    window.location.href = SPLENDID_URL
  }

  function handleEpicerie() {
    window.location.href = EPICERIE_URL
  }

  function handleRestaurant() {
    window.location.href = RESTAURANT_URL
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-12"
      style={{ background: '#f5f5f7' }}
    >
      {/* En-tete */}
      <div className="text-center mb-12">
        <p className="text-[12px] font-semibold uppercase tracking-[.1em] text-[#a1a1a6] mb-3">
          CaroCorp Suite
        </p>
        <h1 className="text-[32px] font-bold tracking-[-0.6px] text-[#1d1d1f]">
          Choisissez votre espace
        </h1>
        <p className="mt-2 text-[15px] text-[#6e6e73]">
          Selectionnez l'application que vous souhaitez utiliser.
        </p>
      </div>

      {/* Cartes — 4 apps */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl">
        <AppCard
          logo={<MarvelineLogo />}
          name={brand.name}
          description="Location evenementielle (vaisselle, mobilier)."
          accentColor={brand.colors.primary}
          onClick={handleMarveline}
        />
        <AppCard
          logo={<SplendidLogo />}
          name="Le Splendid"
          description="Salle de reception evenementielle."
          accentColor="#b8860b"
          onClick={handleSplendid}
        />
        <AppCard
          logo={<EpicerieLogo />}
          name="Epicerie"
          description="Stock, ventes et fournisseurs epicerie."
          accentColor="#059669"
          onClick={handleEpicerie}
        />
        <AppCard
          logo={<RestaurantLogo />}
          name="Restaurant"
          description="Commandes, marmites et menu service."
          accentColor="#d97706"
          onClick={handleRestaurant}
        />
      </div>

      {/* Footer discret */}
      <p className="mt-16 text-[11px] text-[#a1a1a6]">
        CaroCorp Suite
      </p>
    </div>
  )
}
