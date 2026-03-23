import { useI18n } from '../i18n'
import type { AppState, LanguagePreference, NotificationPolicy, ThemeMode } from '../types'

interface SettingsPageProps {
  state: AppState
  onThemeChange: (theme: ThemeMode) => void
  onLanguageChange: (language: LanguagePreference) => void
  onAutostartChange: (enabled: boolean) => void
  onNotificationPolicyChange: (policy: NotificationPolicy) => void
  onExportDiagnostics: () => void
}

export function SettingsPage({
  state,
  onThemeChange,
  onLanguageChange,
  onAutostartChange,
  onNotificationPolicyChange,
  onExportDiagnostics,
}: SettingsPageProps) {
  const { t } = useI18n()
  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>{t('settings.title')}</h2>
        <div className="settings-grid">
          <label className="field-row">
            <span>{t('settings.theme')}</span>
            <select
              aria-label={t('settings.theme')}
              value={state.ui.themeMode}
              onChange={(event) => onThemeChange(event.target.value as ThemeMode)}
            >
              <option value="system">{t('settings.theme.system')}</option>
              <option value="light">{t('settings.theme.light')}</option>
              <option value="dark">{t('settings.theme.dark')}</option>
            </select>
          </label>

          <label className="field-row">
            <span>{t('settings.language')}</span>
            <select
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

          <label className="toggle-row">
            <span>{t('settings.startWithWindows')}</span>
            <input
              type="checkbox"
              checked={state.startup.autostart}
              onChange={(event) => onAutostartChange(event.target.checked)}
            />
          </label>

          <label className="field-row">
            <span>{t('settings.notificationPolicy')}</span>
            <select
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

      <article className="surface-card">
        <h3>{t('settings.diagnostics')}</h3>
        <p className="muted">{state.diagnostics.lastProbe}</p>
        <p className="muted">{state.diagnostics.probeResult}</p>
        <button type="button" className="secondary-button" onClick={onExportDiagnostics}>
          {t('settings.diagnostics.export')}
        </button>
        {state.diagnostics.lastExportPath ? (
          <p className="muted">
            {t('settings.diagnostics.exportedTo', {
              path: state.diagnostics.lastExportPath,
            })}
          </p>
        ) : null}
      </article>

      <article className="surface-card">
        <h3>{t('settings.updates')}</h3>
        <p className="muted">{t('settings.updates.hint')}</p>
        <button type="button" className="secondary-button" disabled>
          {t('settings.updates.button')}
        </button>
      </article>
    </section>
  )
}
