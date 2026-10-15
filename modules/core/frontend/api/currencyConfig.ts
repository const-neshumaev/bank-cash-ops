import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

/** Where the effective configuration of a cash desk comes from. */
export type ConfigSource = 'own' | 'branch' | 'bank' | 'none'

export interface CurrencyOption {
  code: string
  name: string
  symbol: string
  minor_units: number
  is_active?: boolean
}

/** The currencies in force at a cash desk and their source. */
export interface CashDeskCurrencies {
  cash_desk: number
  configured: boolean
  source: ConfigSource
  template_branch_id: number | null
  currencies: CurrencyOption[]
}

/** A currency template; ``defined`` is false when none exists at that scope. */
export interface CurrencyTemplate {
  branch_id: number | null
  defined: boolean
  currencies: CurrencyOption[]
}

export interface CurrencyTemplateSummary {
  branch_id: number | null
  currencies: CurrencyOption[]
}

export async function listActiveCurrencies(): Promise<CurrencyOption[]> {
  const { data } = await api.get<Paginated<CurrencyOption>>('/currencies/', {
    params: { page_size: 100, is_active: true, ordering: 'code' },
  })
  return data.results
}

export async function fetchCashDeskCurrencies(cashDeskId: number): Promise<CashDeskCurrencies> {
  const { data } = await api.get<CashDeskCurrencies>(`/cash-desks/${cashDeskId}/currencies/`)
  return data
}

export async function setCashDeskCurrencies(
  cashDeskId: number,
  codes: string[],
): Promise<CashDeskCurrencies> {
  const { data } = await api.put<CashDeskCurrencies>(`/cash-desks/${cashDeskId}/currencies/`, {
    currencies: codes,
  })
  return data
}

export async function listCurrencyTemplates(): Promise<CurrencyTemplateSummary[]> {
  const { data } = await api.get<{ results: CurrencyTemplateSummary[] }>('/currency-templates/')
  return data.results
}

export async function fetchBankCurrencyTemplate(): Promise<CurrencyTemplate> {
  const { data } = await api.get<CurrencyTemplate>('/currency-templates/bank/')
  return data
}

export async function setBankCurrencyTemplate(codes: string[]): Promise<CurrencyTemplate> {
  const { data } = await api.put<CurrencyTemplate>('/currency-templates/bank/', {
    currencies: codes,
  })
  return data
}

export async function deleteBankCurrencyTemplate(): Promise<void> {
  await api.delete('/currency-templates/bank/')
}

export async function fetchBranchCurrencyTemplate(branchId: number): Promise<CurrencyTemplate> {
  const { data } = await api.get<CurrencyTemplate>(`/currency-templates/branches/${branchId}/`)
  return data
}

export async function setBranchCurrencyTemplate(
  branchId: number,
  codes: string[],
): Promise<CurrencyTemplate> {
  const { data } = await api.put<CurrencyTemplate>(`/currency-templates/branches/${branchId}/`, {
    currencies: codes,
  })
  return data
}

export async function deleteBranchCurrencyTemplate(branchId: number): Promise<void> {
  await api.delete(`/currency-templates/branches/${branchId}/`)
}
