export interface Permission {
  code: string
  name: string
}

export interface Role {
  id: number
  code: string
  name: string
  description: string
  permissions: string[]
  is_system: boolean
  users_count: number
  created_at: string
  updated_at: string
}

export interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  middle_name: string
  full_name: string
  roles: string[]
  roles_display: string[]
  permissions: string[]
  phone: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  date_joined: string
  last_login: string | null
}

export interface Branch {
  id: number
  parent: number | null
  parent_name: string | null
  code: string
  name: string
  address: string
  phone: string
  is_head_office: boolean
  is_active: boolean
  children_count: number
  created_at: string
  updated_at: string
}

export interface CashDesk {
  id: number
  branch: number
  branch_name: string
  code: string
  name: string
  mac_address: string | null
  hostname: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export type ShiftStatus = 'open' | 'closed'

export interface Shift {
  id: number
  cashier: number
  cashier_name: string
  cash_desk: number
  cash_desk_name: string
  cash_desk_code: string
  status: ShiftStatus
  status_display: string
  opened_at: string
  closed_at: string | null
  closed_by: number | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
