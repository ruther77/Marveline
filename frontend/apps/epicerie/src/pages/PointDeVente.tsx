import { useState } from 'react'
import { ShoppingCart, ScanLine } from 'lucide-react'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { CataloguePOS, PanierPOS, ModalEncaissement } from '@/components'
import LoyaltyScanner from '@/components/LoyaltyScanner'
import type { Totaux } from '@/components/PanierPOS'
import type { EpicerieProduitRead, CartItem, EncaissementResponse } from '@/types/epicerie-v2'

const TVA_TAUX_DECIMAL = 0.20

function calcTotaux(items: CartItem[], remiseCentimes: number): Totaux {
  const ttcBrut = items.reduce((s, it) => s + it.produit.prix_unitaire_cts * it.quantite, 0)
  const tvaBrut = Math.round(ttcBrut * TVA_TAUX_DECIMAL / (1 + TVA_TAUX_DECIMAL))
  const htBrut = ttcBrut - tvaBrut
  const remise = Math.min(remiseCentimes, ttcBrut)
  const ttcNet = ttcBrut - remise
  const facteur = ttcBrut > 0 ? ttcNet / ttcBrut : 1
  const tvaNet = Math.round(tvaBrut * facteur)
  return { ttcBrut, tvaBrut, htBrut, ttcNet, tvaNet, htNet: ttcNet - tvaNet, remise }
}

function formatEur(cts: number): string {
  return (cts / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

interface VenteSuccess {
  id: number
  ticket: string
  totalCts: number
}

export default function PointDeVente() {
  const { user } = useMassaCorpAuthStore()
  const isManager = user?.role === 'manager'

  const [items, setItems] = useState<CartItem[]>([])
  const [remiseCentimes, setRemiseCentimes] = useState(0)
  const [remiseMotif, setRemiseMotif] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [venteSuccess, setVenteSuccess] = useState<VenteSuccess | null>(null)
  const [showLoyalty, setShowLoyalty] = useState(false)

  const totaux = calcTotaux(items, remiseCentimes)
  const nbArticles = items.reduce((s, it) => s + it.quantite, 0)

  function addItem(produit: EpicerieProduitRead) {
    setItems(prev => {
      const existing = prev.find(it => it.produit.id === produit.id)
      if (existing) {
        return prev.map(it => it.produit.id === produit.id ? { ...it, quantite: it.quantite + 1 } : it)
      }
      return [...prev, { produit, quantite: 1 }]
    })
  }

  function changeQty(produitId: number, delta: number) {
    setItems(prev =>
      prev.flatMap(it => {
        if (it.produit.id !== produitId) return [it]
        const newQty = it.quantite + delta
        return newQty > 0 ? [{ ...it, quantite: newQty }] : []
      })
    )
  }

  function removeItem(produitId: number) {
    setItems(prev => prev.filter(it => it.produit.id !== produitId))
  }

  function resetPanier() {
    setItems([])
    setRemiseCentimes(0)
    setRemiseMotif('')
    setShowModal(false)
    setVenteSuccess(null)
    setShowLoyalty(false)
  }

  function handleSuccess(res: EncaissementResponse) {
    setShowModal(false)
    setVenteSuccess({
      id: res.id,
      ticket: res.numero_ticket,
      totalCts: res.total_ttc_remise,
    })
  }

  return (
    <div className="h-full flex gap-4 p-4 bg-gray-50 min-h-0">
      {/* Catalogue */}
      <div className="flex-1 flex flex-col bg-white rounded-2xl border border-gray-100 shadow-sm p-4 overflow-hidden min-w-0">
        <h1 className="text-lg font-semibold text-gray-800 mb-4 flex-shrink-0">Point de vente</h1>
        <div className="flex-1 min-h-0">
          <CataloguePOS onAdd={addItem} />
        </div>
      </div>

      {/* Panier */}
      <div className="w-80 xl:w-96 flex-shrink-0 flex flex-col bg-white rounded-2xl border border-gray-100 shadow-sm p-4 overflow-hidden">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2">
            <ShoppingCart className="h-5 w-5 text-blue-600" />
            Panier
            {nbArticles > 0 && (
              <span className="bg-blue-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                {nbArticles}
              </span>
            )}
          </h2>
          {items.length > 0 && (
            <button onClick={resetPanier} className="text-xs text-gray-400 hover:text-red-500 transition-colors">
              Vider
            </button>
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          <PanierPOS
            items={items} totaux={totaux}
            remiseCentimes={remiseCentimes} remiseMotif={remiseMotif}
            isManager={isManager}
            onQtyChange={changeQty} onRemove={removeItem}
            onRemiseChange={(c, m) => { setRemiseCentimes(c); setRemiseMotif(m) }}
            onEncaisser={() => setShowModal(true)}
          />
        </div>
      </div>

      {showModal && (
        <ModalEncaissement
          items={items} ttcNet={totaux.ttcNet}
          remiseCentimes={remiseCentimes} remiseMotif={remiseMotif}
          onSuccess={handleSuccess} onClose={() => setShowModal(false)}
        />
      )}

      {/* Succès paiement — propose le scan fidélité avant nouvelle vente */}
      {venteSuccess && !showLoyalty && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xs p-6 text-center space-y-4">
            <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h3 className="font-bold text-gray-800 text-lg">Vente enregistrée</h3>
              <p className="text-sm text-gray-400">Ticket n° {venteSuccess.ticket}</p>
              <p className="text-sm font-semibold text-gray-700 mt-1">{formatEur(venteSuccess.totalCts)}</p>
            </div>
            <button
              onClick={() => setShowLoyalty(true)}
              className="w-full py-2.5 bg-emerald-600 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity flex items-center justify-center gap-2 min-h-[44px]"
            >
              <ScanLine className="w-4 h-4" />
              Scanner fidélité
            </button>
            <button
              onClick={resetPanier}
              className="w-full py-2.5 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-colors min-h-[44px]"
            >
              Nouvelle vente
            </button>
          </div>
        </div>
      )}

      {/* Scanner fidélité overlay */}
      {venteSuccess && showLoyalty && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="flex flex-col items-center gap-3 w-full max-w-sm">
            <LoyaltyScanner
              venteId={venteSuccess.id}
              totalCts={venteSuccess.totalCts}
              onClose={() => setShowLoyalty(false)}
            />
            <button
              onClick={resetPanier}
              className="text-[12px] text-white/80 hover:text-white underline"
            >
              Passer — Nouvelle vente
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
