import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

export interface BaseValue {
  id: number
  effective_from: string
  amount: string
  currency_code: string
  created_at: string
  updated_at: string
}

export interface BaseValuePayload {
  effective_from: string
  amount: string
}

export async function listBaseValues(): Promise<BaseValue[]> {
  const { data } = await api.get<Paginated<BaseValue>>('/base-values/', {
    params: { page_size: 100, ordering: '-effective_from' },
  })
  return data.results
}

export async function createBaseValue(payload: BaseValuePayload): Promise<BaseValue> {
  const { data } = await api.post<BaseValue>('/base-values/', payload)
  return data
}

export async function updateBaseValue(
  id: number,
  payload: BaseValuePayload,
): Promise<BaseValue> {
  const { data } = await api.patch<BaseValue>(`/base-values/${id}/`, payload)
  return data
}

export async function deleteBaseValue(id: number): Promise<void> {
  await api.delete(`/base-values/${id}/`)
}
