import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

export interface SlotDef {
  code: string
  name: string
  required: boolean
  fixed_currency: string
  order: number
}

export interface WorkplaceOperation {
  code: string
  name: string
  kind: string
  client_data_policy: 'never' | 'always' | 'threshold'
  requires_client: boolean
  slots: SlotDef[]
}

export interface Currency {
  code: string
  name: string
  symbol: string
  minor_units: number
}

export interface CashBalance {
  cash_desk_id: number
  currency: string
  amount: string
  updated_at: string
}

export interface WorkplaceRate {
  currency: string
  base_currency: string
  rate_type: string
  units: number
  value: string
  value_per_unit: string
  effective_from: string
}

export interface OperationLine {
  slot: string
  currency: string
  amount: string
  rate: string | null
}

export interface Operation {
  id: number
  number: number
  operation_type: string
  operation_type_name: string
  cash_desk_id: number
  shift_id: number
  cashier_id: number
  status: 'posted' | 'reversed'
  status_display: string
  client_name: string
  client_document: string
  comment: string
  posted_at: string
  reversal_of: number | null
  lines: OperationLine[]
}

export interface WorkplaceContext {
  shift_id: number | null
  cash_desk_id: number | null
  currencies: Currency[]
  rates: WorkplaceRate[]
  balances: CashBalance[]
  operations: WorkplaceOperation[]
}

export interface PostOperationPayload {
  operation_type: string
  lines: OperationLine[]
  client_name?: string
  client_document?: string
  comment?: string
  idempotency_key?: string
}

export async function fetchWorkplace(): Promise<WorkplaceContext> {
  const { data } = await api.get<WorkplaceContext>('/operations/workplace/')
  return data
}

export async function listOperations(cashDesk: number): Promise<Operation[]> {
  const { data } = await api.get<Paginated<Operation>>('/operations/operations/', {
    params: { cash_desk: cashDesk, page_size: 20, ordering: '-posted_at' },
  })
  return data.results
}

export async function postOperation(payload: PostOperationPayload): Promise<Operation> {
  const { data } = await api.post<Operation>('/operations/operations/', payload)
  return data
}

export async function reverseOperation(id: number): Promise<Operation> {
  const { data } = await api.post<Operation>(`/operations/operations/${id}/reverse/`, {})
  return data
}
