export type UserRole = 'admin' | 'manager' | 'cashier' | 'operator' | 'auditor'

export interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  middle_name: string
  full_name: string
  role: UserRole
  role_display: string
  phone: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  date_joined: string
  last_login: string | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
