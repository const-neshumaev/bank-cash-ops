import dayjs from 'dayjs'
import 'dayjs/locale/ru'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import ru from './locales/ru.json'

/** Language used when nothing else is known (mirrors the backend fallback). */
export const FALLBACK_LANGUAGE = 'ru'

/** Languages the SPA ships translations for. */
export const SUPPORTED_LANGUAGES: readonly string[] = ['ru', 'en']

const STORAGE_KEY = 'bco.language'

function isSupported(code: string | null | undefined): code is string {
  return Boolean(code) && SUPPORTED_LANGUAGES.includes(code as string)
}

/** The persisted user choice, if it is a supported language. */
export function storedLanguage(): string | null {
  const stored = localStorage.getItem(STORAGE_KEY)
  return isSupported(stored) ? stored : null
}

function detectLanguage(): string {
  const stored = storedLanguage()
  if (stored) {
    return stored
  }
  const fromBrowser = navigator.language?.slice(0, 2)
  if (isSupported(fromBrowser)) {
    return fromBrowser
  }
  return FALLBACK_LANGUAGE
}

function applyLanguageSideEffects(language: string): void {
  dayjs.locale(language === 'ru' ? 'ru' : 'en')
  document.documentElement.lang = language
}

void i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: detectLanguage(),
  fallbackLng: FALLBACK_LANGUAGE,
  interpolation: { escapeValue: false },
  returnNull: false,
})

applyLanguageSideEffects(i18n.language)
i18n.on('languageChanged', applyLanguageSideEffects)

/**
 * Switch the active interface language.
 *
 * The choice is persisted in ``localStorage`` (unless ``persist`` is false) so it
 * survives reloads; the axios client then sends it as ``Accept-Language``.
 */
export function setLanguage(language: string, { persist = true } = {}): void {
  if (persist) {
    localStorage.setItem(STORAGE_KEY, language)
  }
  void i18n.changeLanguage(language)
}

export default i18n
