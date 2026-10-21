import { api } from '@app/api/client'

export type ConversionMode = 'via_base' | 'direct'

export interface BankSettings {
  default_language: string
  enabled_languages: string[]
  base_currency: string
  conversion_mode: ConversionMode
  updated_at: string
}

export async function fetchBankSettings(): Promise<BankSettings> {
  const { data } = await api.get<BankSettings>('/settings/')
  return data
}

export async function updateBankSettings(payload: {
  base_currency: string
  conversion_mode: ConversionMode
}): Promise<BankSettings> {
  const { data } = await api.patch<BankSettings>('/settings/', payload)
  return data
}
