import { api } from '@app/api/client'
import type { Branch, Paginated } from '@app/api/types'

export interface ListBranchesParams {
  page?: number
  pageSize?: number
  search?: string
}

export async function listBranches(params: ListBranchesParams = {}): Promise<Paginated<Branch>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.search) query.search = params.search

  const { data } = await api.get<Paginated<Branch>>('/branches/', { params: query })
  return data
}

/** Fetch every branch, for select inputs. */
export async function listAllBranches(): Promise<Branch[]> {
  const { data } = await api.get<Paginated<Branch>>('/branches/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}

export interface BranchPayload {
  parent: number | null
  code: string
  name: string
  address?: string
  phone?: string
  is_head_office: boolean
  is_active: boolean
}

export async function createBranch(payload: BranchPayload): Promise<Branch> {
  const { data } = await api.post<Branch>('/branches/', payload)
  return data
}

export async function updateBranch(id: number, payload: Partial<BranchPayload>): Promise<Branch> {
  const { data } = await api.patch<Branch>(`/branches/${id}/`, payload)
  return data
}

export async function deleteBranch(id: number): Promise<void> {
  await api.delete(`/branches/${id}/`)
}
