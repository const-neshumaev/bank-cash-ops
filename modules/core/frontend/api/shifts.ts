import { api } from '@app/api/client'
import type { Paginated, Shift } from '@app/api/types'

export interface ListShiftsParams {
  page?: number
  pageSize?: number
  status?: string
}

export async function listShifts(params: ListShiftsParams = {}): Promise<Paginated<Shift>> {
  const query: Record<string, unknown> = {}
  if (params.page) query.page = params.page
  if (params.pageSize) query.page_size = params.pageSize
  if (params.status) query.status = params.status

  const { data } = await api.get<Paginated<Shift>>('/shifts/', { params: query })
  return data
}

/** The current user's open shift, or null when there is none. */
export async function fetchCurrentShift(): Promise<Shift | null> {
  const { data } = await api.get<Shift | null>('/shifts/current/')
  return data
}

export async function openShift(cashDeskId: number): Promise<Shift> {
  const { data } = await api.post<Shift>('/shifts/', { cash_desk: cashDeskId })
  return data
}

export async function closeShift(id: number): Promise<Shift> {
  const { data } = await api.post<Shift>(`/shifts/${id}/close/`)
  return data
}

export async function forceCloseShift(id: number): Promise<Shift> {
  const { data } = await api.post<Shift>(`/shifts/${id}/force-close/`)
  return data
}
