import { api } from '@app/api/client'

export interface BankSettings {
  default_language: string
  enabled_languages: string[]
  base_currency: string
  updated_at: string
}

export async function fetchBankSettings(): Promise<BankSettings> {
  const { data } = await api.get<BankSettings>('/settings/')
  return data
}

export async function updateBankSettings(payload: {
  base_currency: string
}): Promise<BankSettings> {
  const { data } = await api.patch<BankSettings>('/settings/', payload)
  return data
}
