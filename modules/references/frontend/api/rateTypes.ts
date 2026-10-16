import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

/** The fixed principle a bank rate type is based on. */
export type RatePrinciple = 'official' | 'buy' | 'sell' | 'conversion'

/** A bank-managed kind of exchange rate. */
export interface RateType {
  id: number
  code: string
  name: string
  principle: RatePrinciple
  is_system: boolean
  is_active: boolean
  order: number
}

export async function listRateTypes(): Promise<RateType[]> {
  const { data } = await api.get<Paginated<RateType>>('/references/rate-types/', {
    params: { page_size: 100, ordering: 'order' },
  })
  return data.results
}

export interface RateTypePayload {
  code: string
  name: string
  principle: RatePrinciple
  is_active: boolean
  order: number
}

export async function createRateType(payload: RateTypePayload): Promise<RateType> {
  const { data } = await api.post<RateType>('/references/rate-types/', payload)
  return data
}

export async function updateRateType(
  id: number,
  payload: Partial<RateTypePayload>,
): Promise<RateType> {
  const { data } = await api.patch<RateType>(`/references/rate-types/${id}/`, payload)
  return data
}

export async function deleteRateType(id: number): Promise<void> {
  await api.delete(`/references/rate-types/${id}/`)
}
