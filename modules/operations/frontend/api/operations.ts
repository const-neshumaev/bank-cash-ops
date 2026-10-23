import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

export interface SlotDef {
  code: string
  name: string
  required: boolean
  fixed_currency: string
  order: number
  multiple: boolean
  currency_policy: 'any' | 'foreign' | 'base'
  amount_mode: 'input' | 'computed'
  computation: '' | 'multiply' | 'divide'
  stores_rate: boolean
  threshold_basis: boolean
}

export interface WorkplaceOperation {
  code: string
  name: string
  kind: string
  form: 'amount' | 'multi_currency' | 'exchange'
  client_data_policy: 'never' | 'always' | 'threshold'
  requires_client: boolean
  threshold_type: string
  threshold_value: string | null
  threshold_currency: string
  rate_principle: '' | 'buy' | 'sell' | 'conversion'
  rate_type: string
  rate_type_display: string
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
  rate_type_display: string
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
  rate_type?: string
  rate_is_individual?: boolean
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
  has_print_documents?: boolean
  lines: OperationLine[]
}

export interface PrintDocument {
  id: number
  document_type: string
  document_type_name: string
  template_code: string
  template_name: string
  operation_id: number
  operation_type_code: string
  cash_desk_id: number
  number: number
  file_name: string
  created_at: string
}

export interface WorkplaceContext {
  shift_id: number | null
  cash_desk_id: number | null
  base_currency: string
  conversion_mode: 'via_base' | 'direct'
  base_value: string | null
  base_value_date: string | null
  currencies: Currency[]
  rates: WorkplaceRate[]
  balances: CashBalance[]
  operations: WorkplaceOperation[]
}

export interface PostOperationPayload {
  operation_type: string
  lines: OperationLine[]
  /** Code of the exchange slot whose amount the cashier entered. */
  basis_slot?: string
  client_name?: string
  client_document?: string
  comment?: string
  idempotency_key?: string
}

export interface ClientDataRequirement {
  policy: 'never' | 'always' | 'threshold'
  required: boolean
  reason: 'never' | 'always' | 'threshold' | 'below_threshold'
  amount: string | null
  threshold: string | null
  currency: string
}

export interface PreviewOperation {
  operation_type: string
  operation_type_name: string
  lines: OperationLine[]
  client_data: ClientDataRequirement
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

export interface PostedOperation extends Operation {
  print_documents?: PrintDocument[]
}

export async function postOperation(payload: PostOperationPayload): Promise<PostedOperation> {
  const { data } = await api.post<PostedOperation>('/operations/operations/', payload)
  return data
}

export async function previewOperation(payload: PostOperationPayload): Promise<PreviewOperation> {
  const { data } = await api.post<PreviewOperation>('/operations/operations/preview/', payload)
  return data
}

export async function reverseOperation(id: number): Promise<Operation> {
  const { data } = await api.post<Operation>(`/operations/operations/${id}/reverse/`, {})
  return data
}

export async function listOperationDocuments(operationId: number): Promise<PrintDocument[]> {
  const { data } = await api.get<PrintDocument[]>(
    `/printing/operations/${operationId}/documents/`,
  )
  return data
}

export async function downloadPrintDocument(documentId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/printing/documents/${documentId}/file/`, {
    responseType: 'blob',
  })
  return data
}
