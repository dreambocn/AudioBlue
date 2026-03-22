import { createContext, useContext, useMemo, type ReactNode } from 'react'

export type SupportedLanguage = 'zh-CN' | 'en-US'
export type LanguagePreference = 'system' | SupportedLanguage

const messages: Record<SupportedLanguage, Record<string, string>> = {
  'zh-CN': {
    'common.none': '无',
    'devices.empty': '未发现可用音频设备。',
    'automation.empty': '没有可自动化的音频设备。',
    'overview.currentDevice': '当前设备',
    'settings.language': '语言',
    'settings.language.system': '跟随系统',
    'settings.language.zh-CN': '中文',
    'settings.language.en-US': 'English',
  },
  'en-US': {
    'common.none': 'None',
    'devices.empty': 'No supported audio devices found.',
    'automation.empty': 'No audio devices available for automation.',
    'overview.currentDevice': 'Current device',
    'settings.language': 'Language',
    'settings.language.system': 'System',
    'settings.language.zh-CN': 'Chinese',
    'settings.language.en-US': 'English',
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
