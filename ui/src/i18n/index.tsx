import { createContext, useContext, useMemo, type ReactNode } from 'react'

export type SupportedLanguage = 'zh-CN' | 'en-US'
export type LanguagePreference = 'system' | SupportedLanguage

const messages: Record<SupportedLanguage, Record<string, string>> = {
  'zh-CN': {
    'common.none': '无',
  },
  'en-US': {
    'common.none': 'None',
  },
}

interface I18nContextValue {
  language: SupportedLanguage
  preference: LanguagePreference
  t: (key: string) => string
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined)

export function resolveSystemLanguage(rawLanguage?: string): SupportedLanguage {
  const normalized = String(rawLanguage ?? '').toLowerCase()
  if (normalized.startsWith('zh')) {
    return 'zh-CN'
  }
  return 'en-US'
}

export function resolveLanguage(
  preference: LanguagePreference,
  systemLanguage?: string,
): SupportedLanguage {
  if (preference === 'system') {
    return resolveSystemLanguage(systemLanguage)
  }
  return preference
}

interface LanguageProviderProps {
  preference: LanguagePreference
  children: ReactNode
}

export function LanguageProvider({ preference, children }: LanguageProviderProps) {
  const language = resolveLanguage(preference, globalThis.navigator?.language)
  const catalog = messages[language]
  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      preference,
      t: (key: string) => catalog[key] ?? messages['en-US'][key] ?? key,
    }),
    [catalog, language, preference],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within a LanguageProvider.')
  }
  return context
}
