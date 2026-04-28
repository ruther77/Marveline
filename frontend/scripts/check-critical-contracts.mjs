#!/usr/bin/env node
import fs from 'fs'
import path from 'path'

const root = process.cwd()
const srcRoot = path.join(root, 'src')

if (!fs.existsSync(srcRoot)) {
  console.error('Expected to run from frontend/ directory')
  process.exit(2)
}

function read(relPath) {
  const abs = path.join(root, relPath)
  if (!fs.existsSync(abs)) {
    throw new Error(`Missing file: ${relPath}`)
  }
  return fs.readFileSync(abs, 'utf8')
}

function walk(dir) {
  const out = []
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', 'dist', '.tanstack', '.vite', 'coverage'].includes(ent.name)) continue
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) out.push(...walk(p))
    else if (p.endsWith('.ts') || p.endsWith('.tsx')) out.push(p)
  }
  return out
}

const contracts = [
  {
    id: 'ERR-002',
    description: 'Reservation full/assign/complete/remind wired route->page->hook->api',
    rules: [
      { file: 'src/routes/_app/events/$id/index.tsx', contains: ['EventDetailPage'] },
      { file: 'src/pages/events/EventDetailPage.tsx', contains: ['ReservationDetailsModal'] },
      {
        file: 'src/pages/events/components/EventDetailsModal.tsx',
        contains: ['useReservationFull', 'useCompleteReservation', 'useRemindReservationDeposit', 'useAssignReservationUser'],
      },
      { file: 'src/api/queries/useReservations.ts', contains: ['reservationsApi.assignUser', 'reservationsApi.completeReservation', 'reservationsApi.remindDeposit'] },
      { file: 'src/api/reservations.ts', contains: ['/reservations/${id}/full', '/reservations/${id}/assign', '/reservations/${id}/complete', '/reservations/${id}/remind-deposit'] },
    ],
  },
  {
    id: 'ERR-003',
    description: 'Invoice full/audit/remind/damage wired route->page->hook->api',
    rules: [
      { file: 'src/routes/_app/invoices/$id/index.tsx', contains: ['InvoiceDetailModal'] },
      { file: 'src/routes/_app/invoices/$id/audit.tsx', contains: ['InvoiceAuditPage'] },
      { file: 'src/routes/_app/operations/return.$reservationId.tsx', contains: ['ReturnInventoryPage'] },
      { file: 'src/pages/invoices/components/InvoiceDetailModal.tsx', contains: ['useInvoiceFull', 'useRemindInvoice'] },
      { file: 'src/pages/invoices/InvoiceAuditPage.tsx', contains: ['useInvoiceFull', 'useInvoiceAudit'] },
      { file: 'src/pages/operations/ReturnInventoryPage.tsx', contains: ['useCreateDamageInvoice'] },
      { file: 'src/api/queries/useInvoices.ts', contains: ['invoicesApi.getInvoiceFull', 'invoicesApi.getInvoiceAudit', 'invoicesApi.remind', 'invoicesApi.createDamageInvoice'] },
      { file: 'src/api/invoices.ts', contains: ['/invoices/${id}/full', '/invoices/${id}/audit', '/invoices/${invoiceId}/remind', '/invoices/damage'] },
    ],
  },
  {
    id: 'ERR-004',
    description: 'Ventes overdue/payments/patch wired route->page->hook->api',
    rules: [
      { file: 'src/routes/_app/ventes/index.tsx', contains: ['VentesListPage'] },
      { file: 'src/routes/_app/ventes/$id.tsx', contains: ['VenteDetailPage'] },
      { file: 'src/routes/_app/ventes/$id/edit.tsx', contains: ['VenteEditPage'] },
      { file: 'src/pages/ventes/VentesListPage.tsx', contains: ['useVentesOverdue'] },
      { file: 'src/pages/ventes/VenteDetailPage.tsx', contains: ['useVentePayments'] },
      { file: 'src/pages/ventes/VenteEditPage.tsx', contains: ['useUpdateVente', 'useVentePayments'] },
      { file: 'src/api/queries/useVentes.ts', contains: ['ventesApi.listOverdue', 'ventesApi.listPayments', 'ventesApi.update'] },
      { file: 'src/api/ventes.ts', contains: ['/ventes/overdue', '/ventes/${id}/payments', '/ventes/${id}'] },
    ],
  },
  {
    id: 'ERR-007',
    description: 'Evenements incidents unified on canonical /events routes',
    rules: [
      { file: 'src/routes/_app/events/incidents.tsx', contains: ['EvenementsListPage'] },
      { file: 'src/routes/_app/events/$id/incidents.tsx', contains: ['EvenementDetailPage'] },
      { file: 'src/pages/evenements/EvenementDetailPage.tsx', contains: ['useEvenementIncidents', 'useCloseAction', 'useUpdateEventStatus'] },
      { file: 'src/api/queries/useEvenements.ts', contains: ['evenementsApi.listIncidents', 'evenementsApi.closeAction'] },
      { file: 'src/api/evenements.ts', contains: ['/evenements/${id}/incidents', '/action-plan', '/actions/${actionId}/close'] },
    ],
  },
  {
    id: 'ERR-010',
    description: 'Legacy /evenements routes redirect to canonical /events incidents routes',
    rules: [
      { file: 'src/routes/_app/evenements/index.tsx', contains: ['redirect', "to: '/events/incidents'"] },
      { file: 'src/routes/_app/evenements/$id.tsx', contains: ['redirect', "to: '/events/$id/incidents'"] },
      { file: 'src/pages/events/EventsPage.tsx', contains: ['to="/events/incidents"'] },
      { file: 'src/pages/events/EventIdLayout.tsx', contains: ['Incidents', '/events/${id}/incidents'] },
    ],
  },
  {
    id: 'ERR-020',
    description: 'FE/BE contract alignment for reservation/vente statuses and vente signatures',
    rules: [
      {
        file: 'src/types/reservation.ts',
        contains: [
          "'draft'",
          "'confirmed'",
          "'pre_check'",
          "'confirmed_risk'",
          "'delivered'",
          "'extended'",
          "'returned'",
          "'returned_dispute'",
          "'completed'",
          "'cancelled'",
        ],
      },
      {
        file: 'src/types/vente.ts',
        contains: [
          "'draft'",
          "'pending'",
          "'deposit_paid'",
          "'fully_paid'",
          "'overdue'",
          "'refunded'",
          "'cancelled'",
          'created_at: string',
        ],
      },
      {
        file: 'src/api/ventes.ts',
        contains: ['date_from?: string', 'date_to?: string', 'search?: string', '/ventes?${qs}'],
      },
      { file: 'src/pages/ventes/VentesListPage.tsx', contains: ['v.created_at'] },
      { file: 'src/pages/ventes/VenteDetailPage.tsx', contains: ['data.created_at'] },
      {
        file: 'src/pages/ventes/VenteCreatePage.tsx',
        contains: ['payment_due_date: paymentDueDate || undefined'],
        notContains: ['saleDate', 'Date de vente *', 'sale_date'],
      },
      {
        file: 'src/schemas/vente.ts',
        contains: ['customer_id: idSchema', 'payment_due_date: dateIsoSchema.optional()'],
        notContains: ['sale_date'],
      },
    ],
  },
]

const errors = []

for (const contract of contracts) {
  for (const rule of contract.rules) {
    let text = ''
    try {
      text = read(rule.file)
    } catch (err) {
      errors.push(`[${contract.id}] ${String(err.message || err)}`)
      continue
    }
    for (const needle of rule.contains) {
      if (!text.includes(needle)) {
        errors.push(`[${contract.id}] ${rule.file} missing token: ${needle}`)
      }
    }
    for (const needle of (rule.notContains ?? [])) {
      if (text.includes(needle)) {
        errors.push(`[${contract.id}] ${rule.file} unexpected token still present: ${needle}`)
      }
    }
  }
}

const legacyAllowed = new Set([
  'src/routes/_app/evenements/index.tsx',
  'src/routes/_app/evenements/$id.tsx',
  'src/routes/_app/evenements.tsx',
  'src/pages/evenements/EvenementDetailPage.tsx',
])

const legacyScanDirs = ['src/pages', 'src/routes', 'src/components']
for (const relDir of legacyScanDirs) {
  const absDir = path.join(root, relDir)
  if (!fs.existsSync(absDir)) continue
  for (const abs of walk(absDir)) {
    const rel = path.relative(root, abs).replace(/\\/g, '/')
    if (legacyAllowed.has(rel)) continue
    const text = fs.readFileSync(abs, 'utf8')
    if (text.includes('/evenements/$id') || text.includes('to="/evenements"') || text.includes("to: '/evenements'")) {
      errors.push(`[ERR-010] non-canonical legacy route usage in ${rel}`)
    }
  }
}

if (errors.length) {
  console.error('Critical contracts check failed:')
  for (const err of errors) {
    console.error(`- ${err}`)
  }
  process.exit(1)
}

console.log('Critical contracts check passed (ERR-002/003/004/007/010/020).')
