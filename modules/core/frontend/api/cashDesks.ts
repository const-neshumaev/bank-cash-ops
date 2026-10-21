import { api } from '@app/api/client'
import type { CashDesk, CashDeskOption, Paginated } from '@app/api/types'

export interface ListCashDesksParams {
  page?: number
  pageSize?: number
  search?: string
  branch?: number | ''
}

export async function listCashDesks(
  params: ListCashDesksParams = {},
): Promise<Paginated<CashDesk>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.search) query.search = params.search
  if (params.branch) query.branch = params.branch

  const { data } = await api.get<Paginated<CashDesk>>('/cash-desks/', { params: query })
  return data
}

/** Fetch every active cash desk, for select inputs. */
export async function listAllCashDesks(): Promise<CashDesk[]> {
  const { data } = await api.get<Paginated<CashDesk>>('/cash-desks/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}

/**
 * Fetch active cash desks of a branch, for the workplace picker. Available to
 * any authenticated user, including cashiers.
 */
export async function listSelectableCashDesks(
  branchId: number,
  search = '',
): Promise<CashDeskOption[]> {
  const { data } = await api.get<Paginated<CashDeskOption>>('/cash-desks/selectable/', {
    params: { page_size: 100, branch: branchId, search: search || undefined },
  })
  return data.results
}

/**
 * Cash desk options for rate screens. Users with structure access get every
 * cash desk; a cashier falls back to the selectable cash desks of a branch.
 */
export async function listRateCashDeskOptions(
  branchId?: number,
): Promise<CashDeskOption[]> {
  try {
    const rows = await listAllCashDesks()
    return rows.map((desk) => ({
      id: desk.id,
      name: desk.name,
      code: desk.code,
      branch: desk.branch,
    }))
  } catch {
    return branchId ? listSelectableCashDesks(branchId) : []
  }
}

export interface CashDeskPayload {
  branch: number
  code: string | null
  name: string
  mac_address?: string | null
  hostname?: string
  is_active: boolean
  uses_individual_rates: boolean
}

export async function createCashDesk(payload: CashDeskPayload): Promise<CashDesk> {
  const { data } = await api.post<CashDesk>('/cash-desks/', payload)
  return data
}

export async function updateCashDesk(
  id: number,
  payload: Partial<CashDeskPayload>,
): Promise<CashDesk> {
  const { data } = await api.patch<CashDesk>(`/cash-desks/${id}/`, payload)
  return data
}

export async function deleteCashDesk(id: number): Promise<void> {
  await api.delete(`/cash-desks/${id}/`)
}
