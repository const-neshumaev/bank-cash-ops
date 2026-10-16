import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

/** A currency of the ISO 4217 catalogue. */
export interface Currency {
  code: string
  numeric_code: string
  name: string
  symbol: string
  minor_units: number
  is_active: boolean
}

export interface ListCurrenciesParams {
  page?: number
  pageSize?: number
  search?: string
  isActive?: boolean
}

export async function listCurrencies(
  params: ListCurrenciesParams = {},
): Promise<Paginated<Currency>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.search) query.search = params.search
  if (params.isActive !== undefined) query.is_active = params.isActive

  const { data } = await api.get<Paginated<Currency>>('/references/currencies/', { params: query })
  return data
}

export interface CurrencyPayload {
  code: string
  numeric_code?: string
  name: string
  symbol?: string
  minor_units: number
  is_active: boolean
}

export async function createCurrency(payload: CurrencyPayload): Promise<Currency> {
  const { data } = await api.post<Currency>('/references/currencies/', payload)
  return data
}

export async function updateCurrency(
  code: string,
  payload: Partial<CurrencyPayload>,
): Promise<Currency> {
  const { data } = await api.patch<Currency>(`/references/currencies/${code}/`, payload)
  return data
}

export async function deleteCurrency(code: string): Promise<void> {
  await api.delete(`/references/currencies/${code}/`)
}
