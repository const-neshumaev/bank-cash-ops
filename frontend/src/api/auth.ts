import { api, tokenStorage } from './client'
import type { User } from './types'

export interface LoginPayload {
  email: string
  password: string
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login/', payload)
  tokenStorage.set(data.access, data.refresh)
  return data
}

export async function logout(): Promise<void> {
  const refresh = tokenStorage.refresh()
  try {
    if (refresh) {
      await api.post('/auth/logout/', { refresh })
    }
  } finally {
    tokenStorage.clear()
  }
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me/')
  return data
}

export interface UpdateMePayload {
  first_name?: string
  last_name?: string
  middle_name?: string
  phone?: string
}

export async function updateMe(payload: UpdateMePayload): Promise<User> {
  const { data } = await api.patch<User>('/auth/me/', payload)
  return data
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
  new_password_confirm: string
}

export async function changePassword(payload: ChangePasswordPayload): Promise<void> {
  await api.post('/auth/change-password/', payload)
}
