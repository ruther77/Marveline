import { useEffect } from 'react'
import { useProductVariantsList } from '@/api/queries/useProductVariants'

interface VariantSelectProps {
  productId: number
  value?: number
  onChange: (variantId: number | undefined) => void
  className?: string
}

export function VariantSelect({ productId, value, onChange, className }: VariantSelectProps) {
  const { data: variants = [] } = useProductVariantsList(productId)

  useEffect(() => {
    if (variants.length === 1 && value !== variants[0].id) {
      onChange(variants[0].id)
    }
  }, [variants, value, onChange])

  if (variants.length <= 1) return null

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
      className={className ?? 'input text-xs py-1 w-32'}
      aria-label="Variante"
    >
      <option value="">Variante…</option>
      {variants.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label} ({v.available_quantity})
        </option>
      ))}
    </select>
  )
}
