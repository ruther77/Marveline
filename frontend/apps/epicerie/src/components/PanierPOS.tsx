import { useState } from 'react'
import { ShoppingCart, Plus, Minus, Trash2, Tag, CreditCard, X } from 'lucide-react'
import { cn } from '@shared/lib/utils'
import type { CartItem } from '@/types/epicerie-v2'

function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

export interface Totaux {
  ttcBrut: number; tvaBrut: number; htBrut: number
  ttcNet: number; tvaNet: number; htNet: number; remise: number
}

function LignePanier({ item, onQtyChange, onRemove }: {
  item: CartItem; onQtyChange: (delta: number) => void; onRemove: () => void
}) {
  return (
    <div className="flex items-center gap-2 py-2 border-b border-gray-50">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{item.produit.designation_clean}</p>
        <p className="text-xs text-gray-400">{formatEur(item.produit.prix_unitaire_cts)} × {item.quantite}</p>
      </div>
      <div className="flex items-center gap-1">
        <button onClick={() => onQtyChange(-1)} className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 min-h-[44px] min-w-[44px] flex items-center justify-center">
          <Minus className="h-3.5 w-3.5" />
        </button>
        <span className="w-6 text-center text-sm font-medium">{item.quantite}</span>
        <button onClick={() => onQtyChange(1)} className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 min-h-[44px] min-w-[44px] flex items-center justify-center">
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button onClick={onRemove} className="p-1 hover:bg-red-50 rounded-lg text-gray-300 hover:text-red-500 ml-1 min-h-[44px] min-w-[44px] flex items-center justify-center">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <span className="text-sm font-semibold text-gray-700 w-20 text-right">
        {formatEur(item.produit.prix_unitaire_cts * item.quantite)}
      </span>
    </div>
  )
}

function TotauxPanier({ ttcBrut, tvaBrut, htBrut, ttcNet, tvaNet, htNet, remise }: Totaux) {
  return (
    <div className="border-t border-gray-100 pt-3 space-y-1 text-xs">
      <div className="flex justify-between text-gray-400"><span>Sous-total HT</span><span>{formatEur(htBrut)}</span></div>
      <div className="flex justify-between text-gray-400"><span>TVA 20%</span><span>{formatEur(tvaBrut)}</span></div>
      {remise > 0 && (
        <>
          <div className="flex justify-between text-gray-500 font-medium pt-1"><span>Total TTC</span><span>{formatEur(ttcBrut)}</span></div>
          <div className="flex justify-between text-red-500 font-medium"><span>Remise</span><span>−{formatEur(remise)}</span></div>
          <div className="flex justify-between text-gray-400"><span>HT après remise</span><span>{formatEur(htNet)}</span></div>
          <div className="flex justify-between text-gray-400"><span>TVA après remise</span><span>{formatEur(tvaNet)}</span></div>
        </>
      )}
      <div className="flex justify-between text-base font-bold text-gray-900 pt-2 border-t border-gray-200">
        <span>Total TTC</span>
        <span className="text-blue-700">{formatEur(ttcNet)}</span>
      </div>
    </div>
  )
}

function RemisePanier({ ttcBrut, remiseCentimes, remiseMotif, onApply, onClose }: {
  ttcBrut: number; remiseCentimes: number; remiseMotif: string
  onApply: (centimes: number, motif: string) => void; onClose: () => void
}) {
  const [modePct, setModePct] = useState(true)
  const [inputVal, setInputVal] = useState(remiseCentimes > 0 ? String(remiseCentimes / 100) : '')
  const [motif, setMotif] = useState(remiseMotif)

  function apply() {
    const raw = parseFloat(inputVal) || 0
    const centimes = modePct ? Math.round(ttcBrut * raw / 100) : Math.round(raw * 100)
    onApply(Math.min(centimes, ttcBrut), motif)
    onClose()
  }

  return (
    <div className="absolute right-0 top-8 z-10 bg-white border border-gray-200 rounded-xl shadow-xl p-4 w-72">
      <div className="flex justify-between items-center mb-3">
        <span className="font-semibold text-gray-800 text-sm">Appliquer une remise</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex gap-1 mb-3 p-1 bg-gray-100 rounded-lg">
        {(['%', 'EUR'] as const).map(mode => (
          <button key={mode} onClick={() => { setModePct(mode === '%'); setInputVal('') }}
            className={cn('flex-1 py-1 text-xs font-medium rounded-md transition-colors',
              (modePct ? mode === '%' : mode === 'EUR') ? 'bg-white shadow text-blue-600' : 'text-gray-500',
            )}>
            {mode}
          </button>
        ))}
      </div>
      <input type="number" min="0" max={modePct ? 100 : Math.round(ttcBrut / 100)}
        value={inputVal} onChange={e => setInputVal(e.target.value)}
        placeholder={modePct ? 'Ex : 10 (%)' : 'Ex : 500 (XPF)'}
        className="w-full mb-2 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-300 focus:outline-none" />
      <input type="text" value={motif} onChange={e => setMotif(e.target.value)}
        placeholder="Motif (optionnel)"
        className="w-full mb-3 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-300 focus:outline-none" />
      <button onClick={apply}
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
        Appliquer
      </button>
    </div>
  )
}

export interface PanierPOSProps {
  items: CartItem[]
  totaux: Totaux
  remiseCentimes: number
  remiseMotif: string
  isManager: boolean
  onQtyChange: (produitId: number, delta: number) => void
  onRemove: (produitId: number) => void
  onRemiseChange: (centimes: number, motif: string) => void
  onEncaisser: () => void
}

export default function PanierPOS({
  items, totaux, remiseCentimes, remiseMotif, isManager,
  onQtyChange, onRemove, onRemiseChange, onEncaisser,
}: PanierPOSProps) {
  const [showRemise, setShowRemise] = useState(false)

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-gray-300">
        <ShoppingCart className="h-10 w-10 mb-2" />
        <span className="text-sm">Panier vide</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {items.map(item => (
          <LignePanier key={item.produit.id} item={item}
            onQtyChange={delta => onQtyChange(item.produit.id, delta)}
            onRemove={() => onRemove(item.produit.id)} />
        ))}
      </div>

      {isManager && (
        <div className="relative mt-3">
          <button onClick={() => setShowRemise(!showRemise)}
            className={cn('flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-colors w-full',
              remiseCentimes > 0 ? 'border-green-300 bg-green-50 text-green-700' : 'border-gray-200 text-gray-500 hover:border-blue-300',
            )}>
            <Tag className="h-3.5 w-3.5" />
            {remiseCentimes > 0 ? `Remise appliquée : −${formatEur(remiseCentimes)}` : 'Appliquer une remise'}
          </button>
          {showRemise && (
            <RemisePanier ttcBrut={totaux.ttcBrut} remiseCentimes={remiseCentimes}
              remiseMotif={remiseMotif} onApply={onRemiseChange} onClose={() => setShowRemise(false)} />
          )}
        </div>
      )}

      <div className="mt-3"><TotauxPanier {...totaux} /></div>

      <button onClick={onEncaisser}
        className="mt-3 w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2 min-h-[44px]">
        <CreditCard className="h-5 w-5" />
        Encaisser {formatEur(totaux.ttcNet)}
      </button>
    </div>
  )
}
