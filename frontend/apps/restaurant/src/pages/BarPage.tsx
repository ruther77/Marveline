// Route : /_massacorp/restaurant/bar
// Bar · Comptoir — Tickets boissons en attente + catalogue comptoir

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, CheckSquare } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import type { BoissonsTicket, CatalogueBoisson, BoissonsTicketLigne } from '@/types/restaurant-v2'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

function fmtHeure(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

// ─── StatutLigneBadge ─────────────────────────────────────────────────────────

const STATUT_LIGNE_CLS: Record<string, string> = {
  ENVOYEE: 'bg-dark-800 text-dark-200',
  LANCEE:  'bg-blue-600/[.08] text-blue-600',
  PRETE:   'bg-green-700/[.08] text-green-700',
  SERVIE:  'bg-violet-600/[.07] text-violet-600',
}

function StatutBadge({ statut }: { statut: string }) {
  const cls = STATUT_LIGNE_CLS[statut] ?? 'bg-dark-800 text-dark-500'
  return (
    <span className={`text-[10.5px] font-semibold px-2 py-0.5 rounded-full ${cls}`}>{statut}</span>
  )
}

// ─── LigneBoissonRow ─────────────────────────────────────────────────────────

function LigneBoissonRow({ ligne, onMarquerPrete }: {
  ligne: BoissonsTicketLigne
  onMarquerPrete: (id: number) => void
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-dark-700 last:border-b-0">
      <div className="flex-1 min-w-0">
        <span className="text-[13px] font-medium text-dark-50 truncate block">{ligne.variante_nom}</span>
        <span className="text-[11.5px] text-dark-200">
          ×{ligne.quantite} · {fmtEur(ligne.prix_unitaire_cts)} / u
        </span>
      </div>
      <StatutBadge statut={ligne.statut_plat} />
      {ligne.statut_plat === 'LANCEE' && (
        <button
          onClick={() => onMarquerPrete(ligne.ligne_id)}
          className="flex items-center gap-1 px-2 py-1 bg-green-700/[.08] text-green-700 text-[11px] font-semibold rounded-md hover:opacity-80 shrink-0"
        >
          <CheckSquare className="h-3 w-3" />
          Prête
        </button>
      )}
    </div>
  )
}

// ─── TicketCard ───────────────────────────────────────────────────────────────

function TicketCard({ ticket, onServirTout, onAppliquerFormule, onMarquerPrete }: {
  ticket: BoissonsTicket
  onServirTout: (id: number) => void
  onAppliquerFormule: (ticketId: number, varianteId: number) => void
  onMarquerPrete: (ligneId: number) => void
}) {
  return (
    <div className="border border-dark-600 rounded-md overflow-hidden bg-white mb-3">
      <div className="flex items-center justify-between px-4 py-3 bg-dark-800 border-b border-dark-600">
        <div>
          <span className="text-[14px] font-bold text-dark-50">Table {ticket.table_numero}</span>
          <span className="text-[12px] text-dark-500 ml-2">{fmtHeure(ticket.date_ouverture)}</span>
        </div>
        <button
          onClick={() => onServirTout(ticket.commande_id)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 text-white text-[12px] font-semibold rounded-md hover:opacity-90"
        >
          Servir tout
        </button>
      </div>

      {ticket.suggestion_formule && (
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-violet-600/[.07] border-b border-dark-600">
          <span className="text-[12px] text-violet-600 font-medium">
            Formule disponible — {ticket.suggestion_formule.label} : économie {fmtEur(ticket.suggestion_formule.economies_cts)}
          </span>
          <button
            onClick={() => onAppliquerFormule(ticket.commande_id, ticket.suggestion_formule!.variante_formule_id)}
            className="px-2.5 py-1 bg-violet-600 text-white text-[11px] font-semibold rounded-md hover:opacity-90 shrink-0"
          >
            Appliquer
          </button>
        </div>
      )}

      <div>
        {ticket.lignes.map(l => (
          <LigneBoissonRow key={l.ligne_id} ligne={l} onMarquerPrete={onMarquerPrete} />
        ))}
      </div>
    </div>
  )
}

// ─── ColonneGauche ────────────────────────────────────────────────────────────

function ColonneGauche({ error, setError }: { error: string | null; setError: (e: string | null) => void }) {
  const qc = useQueryClient()

  const { data: ticketsData, isLoading } = useQuery({
    queryKey: ['restaurant-bar-tickets'],
    queryFn: () => restaurantApi.getBoissonsEnAttente(),
    staleTime: 10_000,
    refetchInterval: 10_000,
  })

  const marquerPretMutation = useMutation({
    mutationFn: (commandeId: number) => restaurantApi.marquerPret(commandeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-bar-tickets'] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const marquerLignePreteMutation = useMutation({
    mutationFn: (ligneId: number) => restaurantApi.updateStatutPlat(ligneId, 'PRETE'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-bar-tickets'] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const appliquerFormuleMutation = useMutation({
    mutationFn: ({ ticketId, varianteId }: { ticketId: number; varianteId: number }) =>
      restaurantApi.appliquerFormule(ticketId, varianteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-bar-tickets'] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const tickets = ticketsData?.items ?? []

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-5 py-3 border-b border-dark-600">
        <h2 className="text-[14px] font-semibold text-dark-50">Boissons en attente</h2>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {error && (
          <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-red-600/[.08] border border-red-600/20 rounded-md">
            <span className="text-[12px] text-red-600 flex-1">{error}</span>
            <button onClick={() => setError(null)} aria-label="Fermer l'erreur"><X className="h-3.5 w-3.5 text-red-600" /></button>
          </div>
        )}
        {isLoading ? (
          <div className="animate-pulse space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="card rounded-xl h-24" style={{ padding: 0 }} />
            ))}
          </div>
        ) : tickets.length === 0 ? (
          <p className="text-center text-[12px] text-dark-500 py-12">Aucun ticket en attente</p>
        ) : (
          tickets.map(t => (
            <TicketCard
              key={t.commande_id}
              ticket={t}
              onServirTout={(id) => marquerPretMutation.mutate(id)}
              onAppliquerFormule={(ticketId, varianteId) =>
                appliquerFormuleMutation.mutate({ ticketId, varianteId })
              }
              onMarquerPrete={(ligneId) => marquerLignePreteMutation.mutate(ligneId)}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ─── ColonneDroite ────────────────────────────────────────────────────────────

function ColonneDroite({ selectedCommandeId, setError }: {
  selectedCommandeId: number | null
  setError: (e: string | null) => void
}) {
  const qc = useQueryClient()

  const { data: catalogueData, isLoading } = useQuery({
    queryKey: ['restaurant-catalogue-boissons'],
    queryFn: () => restaurantApi.getCatalogueBoissons(),
    staleTime: 300_000,
  })

  const ajouterLigneMutation = useMutation({
    mutationFn: ({ commandeId, varianteId }: { commandeId: number; varianteId: number }) =>
      restaurantApi.ajouterLigne(commandeId, {
        variante_plat_id: varianteId,
        instance_preparation_id: null,
        side_id: null,
        quantite: 1,
        notes: null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-bar-tickets'] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const boissons: CatalogueBoisson[] = catalogueData?.items ?? []
  const categories = Array.from(new Set(boissons.map(b => b.categorie)))

  const handleProduitClick = (b: CatalogueBoisson) => {
    if (!selectedCommandeId) {
      setError("Sélectionnez d'abord une table dans la vue Salle")
      return
    }
    ajouterLigneMutation.mutate({ commandeId: selectedCommandeId, varianteId: b.variante_plat_id })
  }

  return (
    <div className="flex flex-col h-full min-h-0 border-l border-dark-600">
      <div className="px-5 py-3 border-b border-dark-600">
        <h2 className="text-[14px] font-semibold text-dark-50">Catalogue comptoir</h2>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
        {isLoading ? (
          <div className="animate-pulse space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i}>
                <div className="bg-dark-700 rounded h-3 w-20 mb-2" />
                <div className="grid grid-cols-2 gap-2">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div key={j} className="bg-dark-800 border border-dark-700 rounded-md h-14" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <>
            {categories.map(cat => (
              <div key={cat}>
                <h3 className="text-[11px] font-semibold text-dark-500 uppercase tracking-wider mb-2">{cat}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {boissons.filter(b => b.categorie === cat).map(b => (
                    <button
                      key={b.variante_plat_id}
                      onClick={() => handleProduitClick(b)}
                      className="flex flex-col items-start px-3 py-2.5 border border-dark-600 rounded-md bg-white hover:bg-violet-600/[.07] hover:border-violet-600/40 transition-colors text-left"
                    >
                      <span className="text-[12.5px] font-medium text-dark-50 truncate w-full">{b.nom}</span>
                      <span className="text-[11px] text-dark-200 mt-0.5">{fmtEur(b.prix_vente_cts)}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {categories.length === 0 && (
              <p className="text-center text-[12px] text-dark-500 py-8">Catalogue vide</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─── BarPage ─────────────────────────────────────────────────────────────────

export default function BarPage() {
  const [selectedCommandeId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // S'abonne au cache partagé sans polling propre (ColonneGauche fait le polling)
  const { data: ticketsData } = useQuery({
    queryKey: ['restaurant-bar-tickets'],
    queryFn: () => restaurantApi.getBoissonsEnAttente(),
    staleTime: 10_000,
  })
  const ticketCount = ticketsData?.items?.length ?? 0

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="px-7 pt-6 pb-4 border-b border-dark-600 bg-white flex items-start justify-between flex-wrap gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-[22px] font-bold text-dark-50 tracking-tight">Bar · Comptoir</h1>
            <p className="text-[13px] text-dark-200 mt-0.5">Tickets en attente · Service boissons</p>
          </div>
          {ticketCount > 0 && (
            <span className="text-[12px] font-semibold bg-violet-600/[.07] text-violet-600 border border-violet-600/20 rounded-full px-2.5 py-0.5">
              {ticketCount} ticket{ticketCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 grid" style={{ gridTemplateColumns: '55% 45%' }}>
        <ColonneGauche error={error} setError={setError} />
        <ColonneDroite selectedCommandeId={selectedCommandeId} setError={setError} />
      </div>
    </div>
  )
}
