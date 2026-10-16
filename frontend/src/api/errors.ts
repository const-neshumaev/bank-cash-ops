import { isAxiosError } from 'axios'

import i18n from '../i18n'

type ApiErrorData = Record<string, unknown>

/** Convert a DRF validation error payload into a single human readable line. */
export function extractErrorMessage(error: unknown): string {
  if (isAxiosError(error) && error.response?.data) {
    const data = error.response.data as ApiErrorData
    for (const [key, value] of Object.entries(data)) {
      const message = Array.isArray(value) ? value[0] : value
      if (typeof message === 'string') {
        return key === 'detail' || key === 'non_field_errors' ? message : `${key}: ${message}`
      }
    }
  }
  return i18n.t('errors.generic')
}
