import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import {
  GitBranch,
  Camera,
  Layers,
  Calendar,
  BarChart2,
  GitCompare,
  Image,
  Upload,
  QrCode,
  Clock,
  Package,
  Puzzle,
  BookOpen,
  Truck,
} from 'lucide-react'

interface ToolCard {
  icon: React.ComponentType<{ className?: string }>
  label: string
  href: string
  description: string
}

interface Scenario {
  emoji: string
  title: string
  description: string
  tools: ToolCard[]
}

const scenarios: Scenario[] = [
  {
    emoji: '🧩',
    title: 'Qualifier',
    description: 'Structurer et qualifier vos produits',
    tools: [
      { icon: GitBranch, label: 'Variantes', href: '/catalogue/products', description: 'Couleurs, tailles, configs' },
      { icon: Calendar, label: 'Disponibilité', href: '/catalogue/availability', description: 'Calendrier produit' },
      { icon: Layers, label: 'Collections', href: '/catalogue/collections', description: 'Groupes thématiques' },
      { icon: GitCompare, label: 'Comparateur', href: '/catalogue/comparator', description: 'Comparer produits' },
    ],
  },
  {
    emoji: '📷',
    title: 'Documenter & tracer',
    description: 'Médias, QR et historique',
    tools: [
      { icon: Image, label: 'Galerie', href: '/catalogue/media', description: 'Photos & médias' },
      { icon: Upload, label: 'Import', href: '/catalogue/import', description: 'Upload en masse' },
      { icon: QrCode, label: 'QR codes', href: '/catalogue/qr', description: 'Scan & étiquettes' },
      { icon: Clock, label: 'Audit', href: '/catalogue/products', description: 'Historique modifications' },
    ],
  },
  {
    emoji: '🛠️',
    title: "Construire l'offre",
    description: 'Packs, formules et fournisseurs',
    tools: [
      { icon: Puzzle, label: 'Bundles', href: '/catalogue/bundles', description: 'Packs assemblés' },
      { icon: BarChart2, label: 'Builder', href: '/catalogue/builder', description: "Constructeur d'offres" },
      { icon: Package, label: 'Pilotage', href: '/catalogue/pilotage', description: 'Suivi perf produits' },
      { icon: BookOpen, label: 'Formules', href: '/catalogue/formulas', description: 'Formules traiteur' },
      { icon: Truck, label: 'Fournisseurs', href: '/catalogue/suppliers', description: 'Gestion achats' },
    ],
  },
]

export default function ProductToolsPage() {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <PageHeader title="Catalogue · Options avancées" subtitle="Outils de qualification, documentation et construction d'offres" />
      </div>

      <div className="space-y-6">
        {scenarios.map((scenario) => (
          <section key={scenario.title}>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">{scenario.emoji}</span>
              <div>
                <h2 className="text-sm font-semibold">{scenario.title}</h2>
                <p className="text-xs text-dark-400">{scenario.description}</p>
              </div>
            </div>
            <div className="card p-0 overflow-hidden divide-y divide-dark-600">
              {scenario.tools.map((tool) => (
                <Link
                  key={tool.href + tool.label}
                  to={tool.href}
                  className="flex items-center gap-4 px-4 py-4 hover:bg-dark-600 transition-colors"
                >
                  <div className="w-8 h-8 rounded-xl bg-dark-950 flex items-center justify-center shrink-0">
                    <tool.icon className="w-4 h-4 text-primary-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{tool.label}</p>
                    <p className="text-xs text-dark-400">{tool.description}</p>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
