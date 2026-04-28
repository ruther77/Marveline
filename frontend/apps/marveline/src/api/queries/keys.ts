/**
 * Query Keys Factory — source unique de vérité pour toutes les clés TanStack Query.
 * Pattern: tableau hiérarchique → invalidation ciblée possible à n'importe quel niveau.
 *
 * Utilisation :
 *   queryClient.invalidateQueries({ queryKey: queryKeys.devis.all })
 *   queryClient.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
 */

export const queryKeys = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  auth: {
    me: () => ['auth', 'me'] as const,
    csrf: () => ['auth', 'csrf'] as const,
    oauthProviders: () => ['auth', 'oauth', 'providers'] as const,
  },

  // ── Utilisateurs (self-service) ──────────────────────────────────────────
  users: {
    me: () => ['users', 'me'] as const,
  },

  // ── Feature Gates (runtime rollout) ──────────────────────────────────────
  features: {
    all: ['features'] as const,
    checks: () => [...queryKeys.features.all, 'check'] as const,
    check: (flagName: string, tenantId: number) =>
      [...queryKeys.features.checks(), flagName, tenantId] as const,
  },

  // ── Devis ─────────────────────────────────────────────────────────────────
  devis: {
    all: ['devis'] as const,
    stats: () => [...queryKeys.devis.all, 'stats'] as const,
    lists: () => [...queryKeys.devis.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.devis.lists(), params] as const,
    detail: (id: number) => [...queryKeys.devis.all, 'detail', id] as const,
    versions: (id: number) => [...queryKeys.devis.all, 'versions', id] as const,
    modules: (id: number) => [...queryKeys.devis.all, 'modules', id] as const,
    phases: (id: number) => [...queryKeys.devis.all, 'phases', id] as const,
    coverage: (id: number) => [...queryKeys.devis.all, 'coverage', id] as const,
  },

  // ── Réservations ──────────────────────────────────────────────────────────
  reservations: {
    all: ['reservations'] as const,
    stats: () => [...queryKeys.reservations.all, 'stats'] as const,
    lists: () => [...queryKeys.reservations.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.reservations.lists(), params] as const,
    detail: (id: number) => [...queryKeys.reservations.all, 'detail', id] as const,
    full: (id: number) => [...queryKeys.reservations.all, 'full', id] as const,
    deposits: (id: number) => [...queryKeys.reservations.all, 'deposits', id] as const,
    preCheck: (id: number) => [...queryKeys.reservations.all, 'pre-check', id] as const,
    risks: (id: number) => [...queryKeys.reservations.all, 'risks', id] as const,
    inspection: (id: number) => [...queryKeys.reservations.all, 'inspection', id] as const,
    disputeLogs: (id: number) => [...queryKeys.reservations.all, 'dispute-logs', id] as const,
  },

  // ── Ventes ────────────────────────────────────────────────────────────────
  ventes: {
    all: ['ventes'] as const,
    lists: () => [...queryKeys.ventes.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.ventes.lists(), params] as const,
    detail: (id: number) => [...queryKeys.ventes.all, 'detail', id] as const,
    payments: (id: number) => [...queryKeys.ventes.all, 'payments', id] as const,
    overdueAll: () => [...queryKeys.ventes.all, 'overdue'] as const,
    overdue: (params: Record<string, unknown>) =>
      [...queryKeys.ventes.overdueAll(), params] as const,
  },

  // ── Factures ──────────────────────────────────────────────────────────────
  invoices: {
    all: ['invoices'] as const,
    lists: () => [...queryKeys.invoices.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.invoices.lists(), params] as const,
    detail: (id: number) => [...queryKeys.invoices.all, 'detail', id] as const,
    full: (id: number) => [...queryKeys.invoices.all, 'full', id] as const,
    audit: (id: number, limit: number) =>
      [...queryKeys.invoices.all, 'audit', id, limit] as const,
    overdue: () => [...queryKeys.invoices.all, 'overdue'] as const,
    payments: (id: number) => [...queryKeys.invoices.all, 'payments', id] as const,
    creditNotes: (id: number) => [...queryKeys.invoices.all, 'credit-notes', id] as const,
  },

  // ── Événements ────────────────────────────────────────────────────────────
  evenements: {
    all: ['evenements'] as const,
    lists: () => [...queryKeys.evenements.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.evenements.lists(), params] as const,
    detail: (id: number) => [...queryKeys.evenements.all, 'detail', id] as const,
    incidents: (id: number) => [...queryKeys.evenements.all, 'incidents', id] as const,
  },

  // ── Opérations terrain ────────────────────────────────────────────────────
  operations: {
    departure: (reservationId: number) =>
      ['operations', 'departure', reservationId] as const,
    return: (reservationId: number) =>
      ['operations', 'return', reservationId] as const,
  },

  // ── Catalogue ─────────────────────────────────────────────────────────────
  products: {
    all: ['products'] as const,
    lists: () => [...queryKeys.products.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.products.lists(), params] as const,
    detail: (id: number) => [...queryKeys.products.all, 'detail', id] as const,
    lowStock: (params?: Record<string, unknown>) =>
      [...queryKeys.products.all, 'low-stock', params ?? {}] as const,
    audit: (id: number) => [...queryKeys.products.all, 'audit', id] as const,
    maintenances: (id: number) => [...queryKeys.products.all, 'maintenances', id] as const,
    images: (id: number) => [...queryKeys.products.all, 'images', id] as const,
  },

  // ── Collections ───────────────────────────────────────────────────────────
  collections: {
    all: ['collections'] as const,
    list: (params?: Record<string, unknown>) => ['collections', 'list', params ?? {}] as const,
    detail: (id: number) => ['collections', 'detail', id] as const,
  },

  categories: {
    all: ['categories'] as const,
    lists: () => [...queryKeys.categories.all, 'list'] as const,
    list: (activeOnly: boolean) => [...queryKeys.categories.lists(), activeOnly ? 'active' : 'all'] as const,
    tree: () => [...queryKeys.categories.all, 'tree'] as const,
  },

  bundles: {
    all: ['bundles'] as const,
    lists: () => [...queryKeys.bundles.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.bundles.lists(), params] as const,
    detail: (id: number) => [...queryKeys.bundles.all, 'detail', id] as const,
  },

  // ── Clients ───────────────────────────────────────────────────────────────
  customers: {
    all: ['customers'] as const,
    lists: () => [...queryKeys.customers.all, 'list'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.customers.lists(), params] as const,
    detail: (id: number) => [...queryKeys.customers.all, 'detail', id] as const,
    history: (id: number) => [...queryKeys.customers.all, 'history', id] as const,
    rfm: () => [...queryKeys.customers.all, 'rfm'] as const,
    rfmProfile: (id: number) => [...queryKeys.customers.all, 'rfm-profile', id] as const,
  },

  // ── Pricing ───────────────────────────────────────────────────────────────
  pricing: {
    all: ['pricing'] as const,
    rules: (params?: Record<string, unknown>) => [...queryKeys.pricing.all, 'rules', params ?? {}] as const,
    rule: (id: number) => [...queryKeys.pricing.all, 'rule', id] as const,
    simulate: (params: Record<string, unknown>) =>
      [...queryKeys.pricing.all, 'simulate', params] as const,
  },

  // ── Dashboard ─────────────────────────────────────────────────────────────
  dashboard: {
    all: ['dashboard'] as const,
    stats: () => [...queryKeys.dashboard.all, 'stats'] as const,
    finances: (year: number) => [...queryKeys.dashboard.all, 'finances', year] as const,
    analytics: (periodDays: number) => [...queryKeys.dashboard.all, 'analytics', periodDays] as const,
  },

  // ── Inventaire / Stock ────────────────────────────────────────────────────
  inventory: {
    all: ['inventory'] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.inventory.all, 'list', params] as const,
    movements: {
      all: ['inventory', 'movements'] as const,
      lists: () => ['inventory', 'movements', 'list'] as const,
      list: (params: Record<string, unknown>) => ['inventory', 'movements', 'list', params] as const,
      detail: (id: number) => ['inventory', 'movements', 'detail', id] as const,
    },
    stats: () => [...(['inventory'] as const), 'stats'] as const,
    stockItems: (productId: number) => [...(['inventory'] as const), 'stock-items', productId] as const,
    stockItemHistory: (productId: number, itemId: number) => [...(['inventory'] as const), 'stock-items', productId, 'history', itemId] as const,
    pendingInspections: () => [...(['inventory'] as const), 'pending-inspections'] as const,
  },

  // ── Zones de livraison ────────────────────────────────────────────────────
  deliveryZones: {
    all: ['delivery-zones'] as const,
    list: () => [...queryKeys.deliveryZones.all, 'list'] as const,
    detail: (id: number) => [...queryKeys.deliveryZones.all, 'detail', id] as const,
  },

  // ── Variantes produit ─────────────────────────────────────────────────────
  productVariants: {
    list: (productId: number) => ['product-variants', productId] as const,
  },

  // ── Recherche ────────────────────────────────────────────────────────────
  search: {
    results: (q: string, types?: string[]) => ['search', q, types ?? []] as const,
  },

  // ── Types de dommages ───────────────────────────────────────────────────
  damageTypes: {
    all: ['damage-types'] as const,
    detail: (id: number) => ['damage-types', 'detail', id] as const,
  },

  // ── VPN ──────────────────────────────────────────────────────────────────
  vpn: {
    peers: () => ['vpn', 'peers'] as const,
    peer: (id: string) => ['vpn', 'peers', id] as const,
    status: () => ['vpn', 'status'] as const,
    ipPools: () => ['vpn', 'ip-pools'] as const,
  },

  // ── MFA ───────────────────────────────────────────────────────────────────
  mfa: {
    status: () => ['mfa-status'] as const,
  },

  // ── WebAuthn / Passkeys ──────────────────────────────────────────────────
  webauthn: {
    all: ['webauthn'] as const,
    credentials: () => ['webauthn', 'credentials'] as const,
  },

  // ── Admin ─────────────────────────────────────────────────────────────────
  admin: {
    all: ['admin'] as const,
    users: (params?: Record<string, unknown>) => ['admin', 'users', params ?? {}] as const,
    apiKeys: (params?: Record<string, unknown>) => ['admin', 'api-keys', params ?? {}] as const,
    featureFlags: () => ['admin', 'feature-flags'] as const,
    deliveryZones: () => ['admin', 'delivery-zones'] as const,
    auditLogs: (params?: Record<string, unknown>) => ['admin', 'audit-logs', params ?? {}] as const,
    auditUser: (userId: number, params?: Record<string, unknown>) =>
      ['admin', 'audit-logs', 'user', userId, params ?? {}] as const,
    auditEntity: (entityType: string, entityId: number, params?: Record<string, unknown>) =>
      ['admin', 'audit-logs', 'entity', entityType, entityId, params ?? {}] as const,
  },

  // ── Stock ─────────────────────────────────────────────────────────────────
  stock: {
    all: ['stock'] as const,
    list: (params?: Record<string, unknown>) => ['stock', 'list', params ?? {}] as const,
    detail: (productId: number) => ['stock', 'detail', productId] as const,
    levels: () => ['stock', 'levels'] as const,
    reorder: () => ['stock', 'reorder'] as const,
    adjustments: (productId?: number) => ['stock', 'adjustments', productId ?? null] as const,
    inventaire: (id: number) => ['stock', 'inventaire', id] as const,
    coverage: () => ['stock', 'coverage'] as const,
  },

  // ── Catalogue ─────────────────────────────────────────────────────────────
  catalogue: {
    all: ['catalogue'] as const,
    lists: () => ['catalogue', 'list'] as const,
    list: (params: Record<string, unknown>) => ['catalogue', 'list', params] as const,
    detail: (id: number) => ['catalogue', 'detail', id] as const,
    availability: (id: number, params?: Record<string, unknown>) =>
      ['catalogue', 'availability', id, params ?? {}] as const,
    audit: (id: number) => ['catalogue', 'audit', id] as const,
    qr: (id: number) => ['catalogue', 'qr', id] as const,
    suppliers: () => ['catalogue', 'suppliers'] as const,
  },

  // ── Planning ──────────────────────────────────────────────────────────────
  planning: {
    day: (date: string) => ['planning', 'day', date] as const,
    week: (date: string) => ['planning', 'week', date] as const,
    month: (date: string) => ['planning', 'month', date] as const,
    resources: (date: string) => ['planning', 'resources', date] as const,
    today: () => ['planning', 'today'] as const,
    timeline: (params: Record<string, unknown>) => ['planning', 'timeline', params] as const,
  },

  // ── Deposits (vue globale admin) ──────────────────────────────────────────
  deposits: {
    all: ['deposits'] as const,
    lists: () => ['deposits', 'list'] as const,
    list: (params: Record<string, unknown>) => ['deposits', 'list', params] as const,
    summary: () => ['deposits', 'summary'] as const,
  },

  // ── Tresorerie unifiee ──────────────────────────────────────────────────
  treasury: {
    all: ['treasury'] as const,
    entries: (params: Record<string, unknown>) => ['treasury', 'entries', params] as const,
    summary: (params?: Record<string, unknown>) => ['treasury', 'summary', params ?? {}] as const,
  },

  // ── Relances ──────────────────────────────────────────────────────────────
  relances: {
    all: ['relances'] as const,
    lists: () => ['relances', 'list'] as const,
    list: (params?: Record<string, unknown>) => ['relances', 'list', params ?? {}] as const,
    eligible: (params?: Record<string, unknown>) =>
      [...(['relances'] as const), 'eligible', params ?? {}] as const,
    history: (invoiceId: number) =>
      [...(['relances'] as const), 'history', invoiceId] as const,
  },

  // ── Commandes unifiées ────────────────────────────────────────────────────
  orders: {
    all: ['orders'] as const,
    lists: () => ['orders', 'list'] as const,
    list: (params: Record<string, unknown>) => ['orders', 'list', params] as const,
    detail: (orderType: string, orderId: number) => ['orders', 'detail', orderType, orderId] as const,
  },

  // ── Commandes fournisseurs ─────────────────────────────────────────────────
  supplierOrders: {
    all: ['supplier-orders'] as const,
    lists: () => ['supplier-orders', 'list'] as const,
    list: (params: Record<string, unknown>) => ['supplier-orders', 'list', params] as const,
    detail: (id: number) => ['supplier-orders', 'detail', id] as const,
  },

  // ── Fidelite (Loyalty) ──────────────────────────────────────────────────────
  loyalty: {
    all: ['loyalty'] as const,
    dashboard: (programId: number) => ['loyalty', 'dashboard', programId] as const,
    members: () => ['loyalty', 'members'] as const,
    memberList: (params: Record<string, unknown>) => ['loyalty', 'members', 'list', params] as const,
    memberProfile: (id: number) => ['loyalty', 'members', 'profile', id] as const,
    me: () => ['loyalty', 'me'] as const,
    rewards: (programId: number) => ['loyalty', 'rewards', programId] as const,
    flashOffers: () => ['loyalty', 'flash-offers'] as const,
  },
} as const
