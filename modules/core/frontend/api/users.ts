import { api } from '@app/api/client'
import type { BranchAccessEntry, Paginated, User } from '@app/api/types'

export interface ListUsersParams {
  page?: number
  pageSize?: number
  search?: string
  roles?: string
  isActive?: boolean | ''
}

export async function listUsers(params: ListUsersParams = {}): Promise<Paginated<User>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.search) query.search = params.search
  if (params.roles) query.roles = params.roles
  if (params.isActive !== undefined && params.isActive !== '') {
    query.is_active = params.isActive
  }

  const { data } = await api.get<Paginated<User>>('/users/', { params: query })
  return data
}

export interface UserCreatePayload {
  email: string
  password: string
  password_confirm: string
  first_name: string
  last_name: string
  middle_name?: string
  phone?: string
  roles: string[]
  branch_access: BranchAccessEntry[]
  is_active: boolean
}

export type UserUpdatePayload = Partial<Omit<UserCreatePayload, 'password' | 'password_confirm'>>

export async function createUser(payload: UserCreatePayload): Promise<User> {
  const { data } = await api.post<User>('/users/', payload)
  return data
}

export async function updateUser(id: number, payload: UserUpdatePayload): Promise<User> {
  const { data } = await api.patch<User>(`/users/${id}/`, payload)
  return data
}

export async function deleteUser(id: number, permanent = false): Promise<void> {
  await api.delete(`/users/${id}/`, {
    params: permanent ? { permanent: true } : undefined,
  })
}

export async function activateUser(id: number): Promise<User> {
  const { data } = await api.post<User>(`/users/${id}/activate/`)
  return data
}

export async function deactivateUser(id: number): Promise<User> {
  const { data } = await api.post<User>(`/users/${id}/deactivate/`)
  return data
}
