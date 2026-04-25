import { A2dpSourceStatus } from '../components/A2dpSourceStatus'
import { useI18n } from '../i18n'
import type {
  A2dpSourceAvailability,
  AppState,
  BridgeMode,
  DeviceViewModel,
} from '../types'

interface DiagnosticsPageProps {
  state: AppState
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onExportDiagnostics: () => void
}

export function DiagnosticsPage({
  state,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  onExportDiagnostics,
}: DiagnosticsPageProps) {
  const { t } = useI18n()
  const supportBundlePath =
    state.diagnostics.lastSupportBundlePath ?? state.diagnostics.lastExportPath
  const supportBundleTime =
    state.diagnostics.lastSupportBundleAt ?? state.diagnostics.lastExportAt
  const audioRouting = state.diagnostics.audioRouting

  return (
    <section className="page-grid diagnostics-workspace-grid">
      <article className="surface-card diagnostics-hero-card">
        <div className="card-head">
          <div className="card-head-copy">
            <p className="panel-kicker">{t('diagnostics.kicker')}</p>
            <h3>{t('settings.diagnostics')}</h3>
            <p className="muted">{t('diagnostics.description')}</p>
          </div>
          <button type="button" className="primary-button" onClick={onExportDiagnostics}>
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
        <div className="feature-note-tags">
          <span className="feature-note-tag text-wrap-anywhere">
            {t('settings.diagnostics.databasePath', {
              value: state.diagnostics.databasePath ?? t('common.notAvailable'),
            })}
          </span>
          {supportBundlePath ? (
            <span
              className="feature-note-tag text-wrap-anywhere"
              data-testid="diagnostics-support-bundle-path"
              title={supportBundlePath}
            >
              {t('settings.diagnostics.exportedTo', { path: supportBundlePath })}
            </span>
          ) : null}
          {supportBundleTime ? (
            <span className="feature-note-tag text-wrap-anywhere">
              {t('settings.diagnostics.supportBundleTime', { value: supportBundleTime })}
            </span>
          ) : null}
        </div>
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('diagnostics.runtimeTitle')}</h3>
          <span className="status-pill subtle">{state.runtime.bridgeMode}</span>
        </div>
        <div className="details-list diagnostics-detail-list">
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
        </div>
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('diagnostics.audioRoutingTitle')}</h3>
          <span className="status-pill subtle">
            {audioRouting?.validationPhase ?? t('common.notAvailable')}
          </span>
        </div>
        <div className="details-list diagnostics-detail-list">
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
            {t('settings.diagnostics.audioRouting.lastValidatedAt', {
              value: audioRouting?.lastValidatedAt ?? t('common.notAvailable'),
            })}
          </p>
        </div>
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('settings.diagnostics.recentErrors')}</h3>
          <span className="status-pill subtle">{state.diagnostics.recentErrors.length}</span>
        </div>
        <div className="error-list">
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
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('settings.diagnostics.a2dpDetails')}</h3>
        </div>
        <A2dpSourceStatus
          mode="detailed"
          availability={sourceAvailability}
          bridgeMode={bridgeMode}
          totalDevices={totalDevices}
          matchedSourceDevices={matchedSourceDevices}
          debugDevices={debugDevices}
        />
      </article>
    </section>
  )
}
