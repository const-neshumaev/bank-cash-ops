import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

/** Where the effective configuration of a cash desk comes from. */
export type ConfigSource = 'own' | 'branch' | 'bank' | 'none'

export interface OperationOption {
  code: string
  name: string
  kind: string
}

interface OperationTypeRow extends OperationOption {
  is_active: boolean
}

/** The operations in force at a cash desk and their source. */
export interface CashDeskOperations {
  cash_desk_id: number
  configured: boolean
  source: ConfigSource
  template_branch_id: number | null
  operations: OperationOption[]
}

/** An operation template; ``defined`` is false when none exists at that scope. */
export interface OperationTemplate {
  branch_id: number | null
  defined: boolean
  operations: OperationOption[]
}

export interface OperationTemplateSummary {
  id: number
  branch_id: number | null
  operations: OperationOption[]
}

export async function listOperationTypes(): Promise<OperationOption[]> {
  const { data } = await api.get<Paginated<OperationTypeRow>>('/operations/types/', {
    params: { page_size: 100, is_active: true, ordering: 'name' },
  })
  return data.results.map((row) => ({ code: row.code, name: row.name, kind: row.kind }))
}

export async function fetchCashDeskOperations(cashDeskId: number): Promise<CashDeskOperations> {
  const { data } = await api.get<CashDeskOperations>(
    `/operations/cash-desks/${cashDeskId}/operations/`,
  )
  return data
}

export async function setCashDeskOperations(
  cashDeskId: number,
  codes: string[],
): Promise<CashDeskOperations> {
  const { data } = await api.put<CashDeskOperations>(
    `/operations/cash-desks/${cashDeskId}/operations/`,
    { operations: codes },
  )
  return data
}

export async function listOperationTemplates(): Promise<OperationTemplateSummary[]> {
  const { data } = await api.get<{ results: OperationTemplateSummary[] }>(
    '/operations/operation-templates/',
  )
  return data.results
}

export async function fetchBankOperationTemplate(): Promise<OperationTemplate> {
  const { data } = await api.get<OperationTemplate>('/operations/operation-templates/bank/')
  return data
}

export async function setBankOperationTemplate(codes: string[]): Promise<OperationTemplate> {
  const { data } = await api.put<OperationTemplate>('/operations/operation-templates/bank/', {
    operations: codes,
  })
  return data
}

export async function deleteBankOperationTemplate(): Promise<void> {
  await api.delete('/operations/operation-templates/bank/')
}

export async function fetchBranchOperationTemplate(branchId: number): Promise<OperationTemplate> {
  const { data } = await api.get<OperationTemplate>(
    `/operations/operation-templates/branches/${branchId}/`,
  )
  return data
}

export async function setBranchOperationTemplate(
  branchId: number,
  codes: string[],
): Promise<OperationTemplate> {
  const { data } = await api.put<OperationTemplate>(
    `/operations/operation-templates/branches/${branchId}/`,
    { operations: codes },
  )
  return data
}

export async function deleteBranchOperationTemplate(branchId: number): Promise<void> {
  await api.delete(`/operations/operation-templates/branches/${branchId}/`)
}
