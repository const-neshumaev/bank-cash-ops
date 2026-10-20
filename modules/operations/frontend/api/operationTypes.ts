import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

import type { SlotDef } from './operations'

export type ClientDataPolicy = 'never' | 'always' | 'threshold'

export interface OperationTypeSettings {
  code: string
  name: string
  kind: string
  kind_display: string
  is_external: boolean
  client_data_policy: ClientDataPolicy
  client_data_policy_display: string
  threshold_type: string
  threshold_type_display: string
  threshold_value: string | null
  threshold_currency: string
  permission_code: string
  is_active: boolean
  slots: SlotDef[]
}

export interface OperationTypeSettingsPayload {
  client_data_policy: ClientDataPolicy
  threshold_type?: string
  threshold_value?: string | null
  threshold_currency?: string
  is_active: boolean
}

export interface ThresholdTypeOption {
  code: string
  name: string
  requires_currency: boolean
}

export interface CurrencyOption {
  code: string
  name: string
  symbol: string
  minor_units: number
}

export type HistoryValue = string | boolean | null

export interface OperationTypeSettingsChange {
  id: number
  operation_type: string
  changed_at: string
  changed_by_id: number | null
  changed_by_email: string
  changes: Record<string, { before: HistoryValue; after: HistoryValue }>
}

export async function listOperationTypeSettings(): Promise<OperationTypeSettings[]> {
  const { data } = await api.get<Paginated<OperationTypeSettings>>('/operations/types/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}

export async function updateOperationTypeSettings(
  code: string,
  payload: OperationTypeSettingsPayload,
): Promise<OperationTypeSettings> {
  const { data } = await api.patch<OperationTypeSettings>(
    `/operations/types/${encodeURIComponent(code)}/`,
    payload,
  )
  return data
}

export async function fetchOperationTypeHistory(
  code: string,
): Promise<OperationTypeSettingsChange[]> {
  const { data } = await api.get<Paginated<OperationTypeSettingsChange>>(
    `/operations/types/${encodeURIComponent(code)}/history/`,
    { params: { page_size: 100 } },
  )
  return data.results
}

export async function listThresholdTypes(): Promise<ThresholdTypeOption[]> {
  const { data } = await api.get<ThresholdTypeOption[]>('/operations/threshold-types/')
  return data
}

export async function listActiveCurrencies(): Promise<CurrencyOption[]> {
  const { data } = await api.get<Paginated<CurrencyOption>>('/references/currencies/', {
    params: { page_size: 100, is_active: true, ordering: 'code' },
  })
  return data.results
}
