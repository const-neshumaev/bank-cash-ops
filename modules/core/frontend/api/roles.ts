import { api } from '@app/api/client'
import type { Paginated, Permission, Role } from '@app/api/types'

export interface ListRolesParams {
  page?: number
  pageSize?: number
  search?: string
}

export async function listRoles(params: ListRolesParams = {}): Promise<Paginated<Role>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.search) query.search = params.search

  const { data } = await api.get<Paginated<Role>>('/roles/', { params: query })
  return data
}

/** Fetch every role, for select inputs. */
export async function listAllRoles(): Promise<Role[]> {
  const { data } = await api.get<Paginated<Role>>('/roles/', { params: { page_size: 100 } })
  return data.results
}

export async function listPermissions(): Promise<Permission[]> {
  const { data } = await api.get<Permission[]>('/permissions/')
  return data
}

export interface RolePayload {
  name: string
  description?: string
  permissions: string[]
}

export async function createRole(payload: RolePayload): Promise<Role> {
  const { data } = await api.post<Role>('/roles/', payload)
  return data
}

export async function updateRole(id: number, payload: Partial<RolePayload>): Promise<Role> {
  const { data } = await api.patch<Role>(`/roles/${id}/`, payload)
  return data
}

export async function deleteRole(id: number): Promise<void> {
  await api.delete(`/roles/${id}/`)
}
