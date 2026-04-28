import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import { useHasScope } from '@/hooks/useHasScope'
import {
  ClipboardList,
  Users,
  Package,
  Wallet,
  FileText,
  Shield,
  Settings,
  Activity,
  Key,
} from 'lucide-react'

interface DomainCard {
  name: string
  description: string
  href: string
  icon: React.ComponentType<{ className?: string }>
}

const MAIN_DOMAINS: DomainCard[] = [
  {
    name: 'Clients',
    description: 'Base client, relances, analyse RFM',
    href: '/customers',
    icon: Users,
  },
  {
    name: 'Devis',
    description: 'Creer et gerer les devis',
    href: '/devis',
    icon: FileText,
  },
  {
    name: 'Parc materiel',
    description: 'Produits, stock, inventaire, fournisseurs',
    href: '/catalogue/products',
    icon: Package,
  },
  {
    name: 'Finances',
    description: 'Factures, tresorerie, cautions, export',
    href: '/finance',
    icon: Wallet,
  },
  {
    name: 'Profil',
    description: 'Mon compte, securite, 2FA',
    href: '/profile',
    icon: Settings,
  },
]

function DomainCardItem({ card }: { card: DomainCard }) {
  return (
    <Link
      to={card.href}
      className="card flex items-center gap-4 p-4 rounded-xl hover:bg-dark-600 transition-colors min-h-[72px]"
    >
      <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center shrink-0">
        <card.icon className="w-5 h-5 text-primary-400" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-dark-100 truncate">{card.name}</p>
        <p className="text-xs text-dark-400 truncate">{card.description}</p>
      </div>
    </Link>
  )
}

const ADMIN_DOMAINS: DomainCard[] = [
  {
    name: 'Equipe',
    description: 'Utilisateurs et droits',
    href: '/admin/users',
    icon: Users,
  },
  {
    name: 'Parametres',
    description: 'Configuration du tenant',
    href: '/admin/settings',
    icon: Settings,
  },
  {
    name: 'Audit',
    description: 'Journal d\'activite',
    href: '/admin/audit-logs',
    icon: Activity,
  },
  {
    name: 'Cles API',
    description: 'Accès machine-to-machine',
    href: '/admin/api-keys',
    icon: Key,
  },
]

export default function PlusPage() {
  const canAdmin = useHasScope('users:read')

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <PageHeader title="Menu" subtitle="Acces rapide" />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {MAIN_DOMAINS.map((card) => (
          <DomainCardItem key={card.href} card={card} />
        ))}
      </div>

      {canAdmin && (
        <section className="space-y-2">
          <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide px-1 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            Administration
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {ADMIN_DOMAINS.map((card) => (
              <DomainCardItem key={card.href} card={card} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
