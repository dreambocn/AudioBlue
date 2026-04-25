import { useI18n } from '../i18n'
import type {
  AppState,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

interface PreferencesPageProps {
  state: AppState
  onThemeChange: (theme: ThemeMode) => void
  onLanguageChange: (language: LanguagePreference) => void
  onAutostartChange: (enabled: boolean) => void
  onNotificationPolicyChange: (policy: NotificationPolicy) => void
}

export function PreferencesPage({
  state,
  onThemeChange,
  onLanguageChange,
  onAutostartChange,
  onNotificationPolicyChange,
}: PreferencesPageProps) {
  const { t } = useI18n()

  return (
    <section className="page-grid preferences-grid">
      <article className="surface-card compact-card">
        <div className="card-head">
          <div>
            <p className="panel-kicker">{t('preferences.kicker')}</p>
            <h3>{t('preferences.title')}</h3>
          </div>
        </div>
        <div className="settings-stack" data-testid="settings-stack">
          <label className="field-row settings-item">
            <span className="settings-label">{t('settings.theme')}</span>
            <select
              className="themed-select"
              aria-label={t('settings.theme')}
              value={state.ui.themeMode}
              onChange={(event) => onThemeChange(event.target.value as ThemeMode)}
            >
              <option value="system">{t('settings.theme.system')}</option>
              <option value="light">{t('settings.theme.light')}</option>
              <option value="dark">{t('settings.theme.dark')}</option>
            </select>
          </label>

          <label className="field-row settings-item">
            <span className="settings-label">{t('settings.language')}</span>
            <select
              className="themed-select"
              aria-label={t('settings.language')}
              value={state.ui.language}
              onChange={(event) =>
                onLanguageChange(event.target.value as LanguagePreference)
              }
            >
              <option value="system">{t('settings.language.system')}</option>
              <option value="zh-CN">{t('settings.language.zh-CN')}</option>
              <option value="en-US">{t('settings.language.en-US')}</option>
            </select>
          </label>

          <label className="toggle-row settings-item">
            <span className="settings-label">{t('settings.startWithWindows')}</span>
            <input
              className="switch-toggle"
              type="checkbox"
              checked={state.startup.autostart}
              onChange={(event) => onAutostartChange(event.target.checked)}
            />
          </label>

          <label className="field-row settings-item">
            <span className="settings-label">{t('settings.notificationPolicy')}</span>
            <select
              className="themed-select"
              value={state.notifications.policy}
              onChange={(event) =>
                onNotificationPolicyChange(event.target.value as NotificationPolicy)
              }
            >
              <option value="silent">{t('settings.notification.silent')}</option>
              <option value="failures">{t('settings.notification.failures')}</option>
              <option value="all">{t('settings.notification.all')}</option>
            </select>
          </label>
        </div>
      </article>

      <article className="surface-card compact-card">
        <h3>{t('settings.updates')}</h3>
        <div className="feature-note feature-note-subtle">
          <div className="feature-note-header">
            <span className="feature-note-icon" aria-hidden="true">
              ↗
            </span>
            <p className="feature-note-copy">{t('settings.updates.hint')}</p>
          </div>
        </div>
        <button type="button" className="secondary-button" disabled>
          {t('settings.updates.button')}
        </button>
      </article>
    </section>
  )
}
