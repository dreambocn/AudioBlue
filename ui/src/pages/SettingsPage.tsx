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
  // 新旧导出字段并存时优先使用支持包字段，兼容早期 diagnostics 导出路径。
  const supportBundlePath =
    state.diagnostics.lastSupportBundlePath ?? state.diagnostics.lastExportPath
  const supportBundleTime =
    state.diagnostics.lastSupportBundleAt ?? state.diagnostics.lastExportAt
  const audioRouting = state.diagnostics.audioRouting

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h3>{t('settings.title')}</h3>
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

      <article className="surface-card">
        <div className="card-head">
          <h3>{t('settings.diagnostics')}</h3>
          <button type="button" className="secondary-button" onClick={onExportDiagnostics}>
            {t('settings.diagnostics.export')}
          </button>
        </div>
        <div className="diagnostics-grid">
          <div className="diagnostics-stat">
            <span>{t('settings.diagnostics.activityCount')}</span>
            <strong>{state.diagnostics.activityEventCount}</strong>
          </div>
          <div className="diagnostics-stat">
            <span>{t('settings.diagnostics.connectionCount')}</span>
            <strong>{state.diagnostics.connectionAttemptCount}</strong>
          </div>
          <div className="diagnostics-stat">
            <span>{t('settings.diagnostics.logCount')}</span>
            <strong>{state.diagnostics.logRecordCount}</strong>
          </div>
          <div className="diagnostics-stat">
            <span>{t('settings.diagnostics.runtimeMode')}</span>
            <strong>{state.diagnostics.runtimeMode ?? bridgeMode}</strong>
          </div>
        </div>
        <p className="muted">
          {t('settings.diagnostics.databasePath', {
            value: state.diagnostics.databasePath ?? t('common.notAvailable'),
          })}
        </p>
        {supportBundlePath ? (
          <p className="muted">
            {t('settings.diagnostics.exportedTo', {
              path: supportBundlePath,
            })}
          </p>
        ) : null}
        {supportBundleTime ? (
          <p className="muted">
            {t('settings.diagnostics.supportBundleTime', {
              value: supportBundleTime,
            })}
          </p>
        ) : null}
        {/* 技术详情折叠区承接面向排障的状态，不挤占常规设置内容。 */}
        <details className="diagnostics-details">
          <summary>{t('settings.diagnostics.technicalDetails')}</summary>
          <div className="diagnostics-details-content">
            <div className="details-list">
              <p>
                {t('settings.diagnostics.watcher.enumerationCompleted', {
                  value:
                    state.diagnostics.watcher?.initialEnumerationCompleted
                      ? t('common.on')
                      : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.watcher.startupReconnect', {
                  value:
                    state.diagnostics.watcher?.startupReconnectCompleted
                      ? t('common.on')
                      : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.watcher.knownDevices', {
                  value: state.diagnostics.watcher?.knownDeviceCount ?? totalDevices,
                })}
              </p>
              <p>
                {t('settings.diagnostics.watcher.activeConnections', {
                  value: state.diagnostics.watcher?.activeConnectionCount ?? 0,
                })}
              </p>
              <p>
                {t('settings.diagnostics.watcher.serviceShutdown', {
                  value:
                    state.diagnostics.watcher?.serviceShutdown
                      ? t('common.on')
                      : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.currentDevice', {
                  value: audioRouting?.currentDeviceId ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.remoteContainer', {
                  value: audioRouting?.remoteContainerId ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.remoteConnected', {
                  value:
                    audioRouting?.remoteAepConnected === undefined
                      ? t('common.notAvailable')
                      : audioRouting.remoteAepConnected
                        ? t('common.on')
                        : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.remotePresent', {
                  value:
                    audioRouting?.remoteAepPresent === undefined
                      ? t('common.notAvailable')
                      : audioRouting.remoteAepPresent
                        ? t('common.on')
                        : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.localRender', {
                  value: audioRouting?.localRenderName ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.localRenderState', {
                  value: audioRouting?.localRenderState ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.audioFlowObserved', {
                  value:
                    audioRouting?.audioFlowObserved === undefined
                      ? t('common.notAvailable')
                      : audioRouting.audioFlowObserved
                        ? t('common.on')
                        : t('common.off'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.audioFlowPeak', {
                  value:
                    audioRouting?.audioFlowPeakMax === undefined
                      ? t('common.notAvailable')
                      : String(audioRouting.audioFlowPeakMax),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.validationPhase', {
                  value: audioRouting?.validationPhase ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.lastValidatedAt', {
                  value: audioRouting?.lastValidatedAt ?? t('common.notAvailable'),
                })}
              </p>
              <p>
                {t('settings.diagnostics.audioRouting.lastRecoverReason', {
                  value: audioRouting?.lastRecoverReason ?? t('common.notAvailable'),
                })}
              </p>
            </div>
            <div className="error-list">
              <h4>{t('settings.diagnostics.recentErrors')}</h4>
              {state.diagnostics.recentErrors.length === 0 ? (
                <p className="muted">{t('settings.diagnostics.recentErrors.empty')}</p>
              ) : (
                state.diagnostics.recentErrors.map((item, index) => (
                  <article key={`${item.title}-${index}`} className="surface-card compact-card">
                    <strong>{item.title}</strong>
                    {item.detail ? <p className="muted">{item.detail}</p> : null}
                    {item.happenedAt ? <p className="muted">{item.happenedAt}</p> : null}
                    {item.errorCode ? (
                      <p className="muted">
                        {t('overview.activity.code', { value: item.errorCode })}
                      </p>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </div>
        </details>
        {/* A2DP 详情单独折叠，方便用户在“看不到设备”时快速定位 bridge 与筛选状态。 */}
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
