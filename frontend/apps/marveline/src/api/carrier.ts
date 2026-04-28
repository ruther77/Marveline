import { api } from './fetchClient'
import type { CarrierQuote, CarrierQuoteRequest } from '../types/carrier'

export const carrierApi = {
  getQuotes: async (req: CarrierQuoteRequest): Promise<CarrierQuote[]> => {
    return api.post<CarrierQuote[]>('/carrier/quotes', req)
  },
}
