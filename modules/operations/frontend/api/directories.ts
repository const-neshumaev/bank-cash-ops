import { api } from '@app/api/client'
import type { Branch, CashDesk, Paginated } from '@app/api/types'

/**
 * Read the cash desks and branches from the `core` module API.
 *
 * The operations module owns the per-cash-desk operation configuration but not
 * the cash desks themselves, so it reads them over REST (importing another
 * module's frontend code is forbidden).
 */
export async function listCashDesks(): Promise<CashDesk[]> {
  const { data } = await api.get<Paginated<CashDesk>>('/cash-desks/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}

export async function listBranches(): Promise<Branch[]> {
  const { data } = await api.get<Paginated<Branch>>('/branches/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}
