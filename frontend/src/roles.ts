import type { UserRole } from './api/types'

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Администратор',
  manager: 'Руководитель',
  cashier: 'Кассир',
  operator: 'Операционист',
  auditor: 'Аудитор',
}

export const ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as UserRole[]).map((value) => ({
  value,
  label: ROLE_LABELS[value],
}))

export const ROLE_COLORS: Record<UserRole, string> = {
  admin: 'red',
  manager: 'grape',
  cashier: 'blue',
  operator: 'teal',
  auditor: 'orange',
}
