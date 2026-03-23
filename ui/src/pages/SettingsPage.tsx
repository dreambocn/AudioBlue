import { A2dpSourceStatus } from '../components/A2dpSourceStatus'
import { useI18n } from '../i18n'
import type {
  A2dpSourceAvailability,
  AppState,
  BridgeMode,
  DeviceViewModel,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

interface SettingsPageProps {
  state: AppState
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onThemeChange: (theme: ThemeMode) => void
  onLanguageChange: (language: LanguagePreference) => void
  onAutostartChange: (enabled: boolean) => void
  onNotificationPolicyChange: (policy: NotificationPolicy) => void
  onExportDiagnostics: () => void
}

export function SettingsPage({
  state,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
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
        <h3>{t('settings.title')}</h3>
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
        <div className="card-head">
          <h3>{t('settings.diagnostics')}</h3>
          <button type="button" className="secondary-button" onClick={onExportDiagnostics}>
            {t('settings.diagnostics.export')}
          </button>
        </div>
        <p className="muted">{state.diagnostics.lastProbe}</p>
        <p className="muted">{state.diagnostics.probeResult}</p>
        {state.diagnostics.lastExportPath ? (
          <p className="muted">
            {t('settings.diagnostics.exportedTo', {
              path: state.diagnostics.lastExportPath,
            })}
          </p>
        ) : null}
        <details className="diagnostics-details">
          <summary>{t('settings.diagnostics.a2dpDetails')}</summary>
          <div className="diagnostics-details-content">
            <A2dpSourceStatus
              mode="detailed"
              availability={sourceAvailability}
              bridgeMode={bridgeMode}
              totalDevices={totalDevices}
              matchedSourceDevices={matchedSourceDevices}
              debugDevices={debugDevices}
            />
          </div>
        </details>
      </article>

      <article className="surface-card compact-card">
        <h3>{t('settings.updates')}</h3>
        <p className="muted">{t('settings.updates.hint')}</p>
        <button type="button" className="secondary-button" disabled>
          {t('settings.updates.button')}
        </button>
      </article>
    </section>
  )
}
