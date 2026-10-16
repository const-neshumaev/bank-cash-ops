import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { api } from '../api/client'
import i18n, { FALLBACK_LANGUAGE, setLanguage, storedLanguage } from './index'

interface BankSettingsResponse {
  default_language: string
  enabled_languages: string[]
}

interface LanguageContextValue {
  /** The active interface language. */
  language: string
  /** Languages offered by the bank (from `/api/settings/`). */
  languages: string[]
  /** The bank-wide default language. */
  defaultLanguage: string
  /** Switch the interface language and persist the choice. */
  changeLanguage: (code: string) => void
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined)

/**
 * Provides the bank's language settings to the SPA.
 *
 * The bank-wide defaults come from the public `/api/settings/` endpoint; the
 * per-user choice is applied by the auth flow (`AuthContext`).
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setCurrent] = useState(i18n.language)
  const [languages, setLanguages] = useState<string[]>([FALLBACK_LANGUAGE])
  const [defaultLanguage, setDefaultLanguage] = useState(FALLBACK_LANGUAGE)

  useEffect(() => {
    let cancelled = false
    void api
      .get<BankSettingsResponse>('/settings/')
      .then(({ data }) => {
        if (cancelled) {
          return
        }
        setLanguages(
          data.enabled_languages.length ? data.enabled_languages : [data.default_language],
        )
        setDefaultLanguage(data.default_language)
        // With no explicit choice yet, follow the bank-wide default.
        if (!storedLanguage() && data.default_language && data.default_language !== i18n.language) {
          void i18n.changeLanguage(data.default_language)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const handle = (next: string) => setCurrent(next)
    i18n.on('languageChanged', handle)
    return () => {
      i18n.off('languageChanged', handle)
    }
  }, [])

  const changeLanguage = useCallback((code: string) => setLanguage(code), [])

  const value = useMemo<LanguageContextValue>(
    () => ({ language, languages, defaultLanguage, changeLanguage }),
    [language, languages, defaultLanguage, changeLanguage],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}
