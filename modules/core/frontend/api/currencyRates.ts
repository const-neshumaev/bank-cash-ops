import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

/** How a rate of a bank rate type is stored and applied. */
export type RateValidity = 'calendar_day' | 'since_set'

/** Where a rate is set: the bank, a branch or a cash desk. */
export type RateScope = 'bank' | 'branch' | 'cash_desk'

export interface RateType {
  id: number
  code: string
  name: string
  principle: 'official' | 'buy' | 'sell' | 'conversion'
  validity: RateValidity
  daily_required: boolean
  is_active: boolean
  order: number
}

export interface CurrencyRate {
  id: number
  currency: string
  base_currency: string
  rate_type: string
  units: number
  value: string
  branch: number | null
  branch_name: string | null
  cash_desk: number | null
  cash_desk_name: string | null
  scope: RateScope
  effective_date: string | null
  effective_from: string
  is_current: boolean
  superseded_at: string | null
  created_by: number | null
  created_by_email: string | null
  created_at: string
  updated_at: string
}

export interface RateFilters {
  currency?: string
  base_currency?: string
  rate_type?: string
  scope?: RateScope | ''
  branch?: number | ''
  cash_desk?: number | ''
  effective_date_from?: string
  effective_date_to?: string
  effective_from_from?: string
  effective_from_to?: string
  created_from?: string
  created_to?: string
  created_by?: number | ''
  is_current?: boolean
  at?: string
  page?: number
  pageSize?: number
}

export interface RateItem {
  currency: string
  units: number
  value: string
}

export interface BulkRatePayload {
  rate_type: string
  base_currency?: string
  branch?: number | null
  cash_desk?: number | null
  effective_date?: string | null
  effective_from?: string | null
  items: RateItem[]
}

function queryFromFilters(filters: RateFilters): Record<string, unknown> {
  const query: Record<string, unknown> = {}
  if (filters.page) query.page = filters.page
  if (filters.pageSize) query.page_size = filters.pageSize
  if (filters.currency) query.currency = filters.currency
  if (filters.base_currency) query.base_currency = filters.base_currency
  if (filters.rate_type) query.rate_type = filters.rate_type
  if (filters.scope) query.scope = filters.scope
  if (filters.branch) query.branch = filters.branch
  if (filters.cash_desk) query.cash_desk = filters.cash_desk
  if (filters.effective_date_from) query.effective_date_from = filters.effective_date_from
  if (filters.effective_date_to) query.effective_date_to = filters.effective_date_to
  if (filters.effective_from_from) query.effective_from_from = filters.effective_from_from
  if (filters.effective_from_to) query.effective_from_to = filters.effective_from_to
  if (filters.created_from) query.created_from = filters.created_from
  if (filters.created_to) query.created_to = filters.created_to
  if (filters.created_by) query.created_by = filters.created_by
  if (filters.is_current !== undefined) query.is_current = filters.is_current
  if (filters.at) query.at = filters.at
  return query
}

export async function listRateTypes(): Promise<RateType[]> {
  const { data } = await api.get<Paginated<RateType>>('/references/rate-types/', {
    params: { page_size: 100, ordering: 'order' },
  })
  return data.results
}

/** The rate journal: every rate ever set, including superseded versions. */
export async function listRates(filters: RateFilters = {}): Promise<Paginated<CurrencyRate>> {
  const { data } = await api.get<Paginated<CurrencyRate>>('/currency-rates/', {
    params: queryFromFilters(filters),
  })
  return data
}

/** Rates in force at the moment (or at ``at``), optionally pre-filtered. */
export async function listCurrentRates(
  filters: RateFilters = {},
): Promise<Paginated<CurrencyRate>> {
  const { data } = await api.get<Paginated<CurrencyRate>>('/currency-rates/current/', {
    params: queryFromFilters(filters),
  })
  return data
}

/** Every current rate matching the filters, across pages (for the entry grid). */
export async function listAllCurrentRates(
  filters: RateFilters = {},
): Promise<CurrencyRate[]> {
  const results: CurrencyRate[] = []
  let page = 1
  for (;;) {
    const data = await listCurrentRates({ ...filters, page, pageSize: 100 })
    results.push(...data.results)
    if (!data.next) break
    page += 1
  }
  return results
}

/**
 * Set many rates of one type and scope; a calendar-day rate of the same date is
 * replaced by a new version.
 */
export async function bulkSetRates(payload: BulkRatePayload): Promise<CurrencyRate[]> {
  const { data } = await api.post<CurrencyRate[]>('/currency-rates/bulk/', payload)
  return data
}

export interface ConversionPairItem {
  currency: string
  base_currency: string
  units: number
  buy: string
  sell: string
}

export interface ConversionBulkPayload {
  branch?: number | null
  cash_desk?: number | null
  effective_date?: string | null
  effective_from?: string | null
  pairs: ConversionPairItem[]
}

/** Set direct conversion pairs with both buy and sell quotes. */
export async function conversionBulkSet(
  payload: ConversionBulkPayload,
): Promise<CurrencyRate[]> {
  const { data } = await api.post<CurrencyRate[]>(
    '/currency-rates/conversion-bulk/',
    payload,
  )
  return data
}

export interface CreateRatePayload {
  rate_type: string
  currency: string
  base_currency?: string
  units?: number
  value: string
  branch?: number | null
  cash_desk?: number | null
  effective_date?: string | null
  effective_from?: string | null
}

export async function createRate(payload: CreateRatePayload): Promise<CurrencyRate> {
  const { data } = await api.post<CurrencyRate>('/currency-rates/', payload)
  return data
}
