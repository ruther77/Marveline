import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/layout/SubNav'
import { BarChart3, FileText, Wallet, CalendarRange, Shield, ArrowLeftRight, Download, TrendingUp } from 'lucide-react'

const FINANCE_NAV = [
  { label: 'Synthese',       href: '/finance',                        icon: <BarChart3 className="w-4 h-4" /> },
  { label: 'Analytiques',    href: '/finance/analytics',              icon: <TrendingUp className="w-4 h-4" /> },
  { label: 'Factures',       href: '/finance/invoices',               icon: <FileText className="w-4 h-4" /> },
  { label: 'Tresorerie',     href: '/finance/treasury',               icon: <Wallet className="w-4 h-4" /> },
  { label: 'Cautions',       href: '/finance/invoices/cautions',      icon: <Shield className="w-4 h-4" /> },
  { label: 'Rapprochement',  href: '/finance/invoices/rapprochement', icon: <ArrowLeftRight className="w-4 h-4" /> },
  { label: 'Periodes',       href: '/finance/period',                 icon: <CalendarRange className="w-4 h-4" /> },
  { label: 'Export',         href: '/finance/export',                 icon: <Download className="w-4 h-4" /> },
]

export const Route = createFileRoute('/_app/finance')({
  component: () => (
    <div>
      <SubNav items={FINANCE_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
