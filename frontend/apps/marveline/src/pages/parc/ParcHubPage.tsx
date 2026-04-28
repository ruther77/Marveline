import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import {
  Package,
  Search,
  Wrench,
  Boxes,
  ArrowLeftRight,
  ClipboardCheck,
  RotateCcw,
  Truck,
  Layers,
  Calculator,
  BarChart3,
  AlertTriangle,
  QrCode,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Section card ─────────────────────────────────────────────────────────────

interface HubCard {
  label: string
  description: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  highlight?: boolean
}

function HubCardItem({ card }: { card: HubCard }) {
  return (
    <Link
      to={card.href}
      className={cn(
        'card p-4 flex items-start gap-4 transition-all hover:ring-1 hover:ring-primary-500/30 active:scale-[0.98] min-h-[44px]',
        card.highlight && 'ring-1 ring-primary-500/20 bg-primary-500/5',
      )}
    >
      <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0', card.color)}>
        <card.icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{card.label}</p>
        <p className="text-xs text-dark-400 mt-0.5">{card.description}</p>
      </div>
    </Link>
  )
}

// ── Sections ─────────────────────────────────────────────────────────────────

const CATALOGUE_SECTION: HubCard[] = [
  {
    label: 'Produits',
    description: 'Liste complète du catalogue',
    href: '/catalogue/products',
    icon: Package,
    color: 'bg-primary-500/15 text-primary-400',
  },
  {
    label: 'Recherche catalogue',
    description: 'Recherche avancée, filtres, QR',
    href: '/catalogue/search',
    icon: Search,
    color: 'bg-blue-900/40 text-blue-400',
    highlight: true,
  },
  {
    label: 'Collections',
    description: 'Groupements de produits',
    href: '/catalogue/collections',
    icon: Layers,
    color: 'bg-violet-900/40 text-violet-400',
  },
  {
    label: 'Formules',
    description: 'Packs et offres groupées',
    href: '/catalogue/formulas',
    icon: Calculator,
    color: 'bg-teal-900/40 text-teal-400',
  },
  {
    label: 'QR Codes',
    description: 'Scanner et générer des QR',
    href: '/catalogue/qr',
    icon: QrCode,
    color: 'bg-dark-900 text-dark-300',
  },
]

const STOCK_SECTION: HubCard[] = [
  {
    label: 'Stock',
    description: 'État du stock en temps réel',
    href: '/stock/items',
    icon: Boxes,
    color: 'bg-emerald-900/40 text-emerald-400',
  },
  {
    label: 'Opérations',
    description: 'Départs, retours, contrôles terrain',
    href: '/operations',
    icon: ArrowLeftRight,
    color: 'bg-cyan-900/40 text-cyan-400',
  },
  {
    label: 'Planning réparations',
    description: 'Retours endommagés et maintenances',
    href: '/stock/repairs',
    icon: Wrench,
    color: 'bg-orange-900/40 text-orange-400',
    highlight: true,
  },
  {
    label: 'Inventaire physique',
    description: 'Comptage et ajustements terrain',
    href: '/stock/inventory',
    icon: ClipboardCheck,
    color: 'bg-yellow-900/40 text-yellow-400',
  },
  {
    label: 'Types de dommages',
    description: 'Référentiel des dégradations',
    href: '/stock/damage-types',
    icon: AlertTriangle,
    color: 'bg-red-900/40 text-red-400',
  },
]

const SUPPLIERS_SECTION: HubCard[] = [
  {
    label: 'Fournisseurs',
    description: 'Annuaire et commandes',
    href: '/catalogue/suppliers',
    icon: Truck,
    color: 'bg-amber-900/40 text-amber-400',
  },
  {
    label: 'Pilotage',
    description: 'Indicateurs et couverture stock',
    href: '/catalogue/pilotage',
    icon: BarChart3,
    color: 'bg-indigo-900/40 text-indigo-400',
  },
]

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ParcHubPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Package className="w-5 h-5 text-primary-400" />
        <PageHeader title="Parc" subtitle="Catalogue, stock, inventaire et fournisseurs" />
      </div>

      {/* Catalogue */}
      <section>
        <h2 className="text-xs font-medium text-dark-400 uppercase tracking-wide mb-4">
          Catalogue
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {CATALOGUE_SECTION.map((card) => (
            <HubCardItem key={card.href} card={card} />
          ))}
        </div>
      </section>

      {/* Stock & Inventaire */}
      <section>
        <h2 className="text-xs font-medium text-dark-400 uppercase tracking-wide mb-4">
          Stock & Inventaire
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {STOCK_SECTION.map((card) => (
            <HubCardItem key={card.href} card={card} />
          ))}
        </div>
      </section>

      {/* Fournisseurs & Pilotage */}
      <section>
        <h2 className="text-xs font-medium text-dark-400 uppercase tracking-wide mb-4">
          Fournisseurs & Pilotage
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {SUPPLIERS_SECTION.map((card) => (
            <HubCardItem key={card.href} card={card} />
          ))}
        </div>
      </section>
    </div>
  )
}
