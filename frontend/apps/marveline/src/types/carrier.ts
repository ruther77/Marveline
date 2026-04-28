export interface CarrierQuote {
  carrier_name: string
  carrier_code: string
  service_name: string
  price_cents: number
  delivery_days: number | null
  currency: string
}

export interface CarrierQuoteRequest {
  weight_grams: number
  volume_cm3?: number
  length_cm?: number
  width_cm?: number
  height_cm?: number
  destination_postal_code: string
  destination_country?: string
}
