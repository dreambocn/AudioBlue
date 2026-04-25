import { useI18n } from '../i18n'
import type {
  A2dpSourceAvailability,
  AppState,
  DeviceViewModel,
} from '../types'

interface CockpitPageProps {
  state: AppState
  activeDevice?: DeviceViewModel
  candidateDevice?: DeviceViewModel
  sourceAvailability: A2dpSourceAvailability
  onOpenDiagnostics: () => void
}

export function CockpitPage({
  state,
  activeDevice,
  candidateDevice,
  sourceAvailability,
  onOpenDiagnostics,
}: CockpitPageProps) {
  const { t } = useI18n()

  const connectionTitle = activeDevice?.name ?? candidateDevice?.name ?? t('common.none')

  return (
    <section className="page-grid cockpit-grid">
      <article className="surface-card spotlight-card cockpit-hero">
        <div className="cockpit-hero-copy">
          <p className="panel-kicker">{t('cockpit.kicker')}</p>
          <h3>{t('cockpit.title')}</h3>
          <h4 className="text-truncate" title={connectionTitle}>
            {connectionTitle}
          </h4>
          <p className="muted">{t('cockpit.description')}</p>
        </div>
        <div className="cockpit-hero-status">
          <span className={`status-pill ${state.connection.status}`}>
            {t(`overview.status.${state.connection.currentPhase ?? state.connection.status}`)}
          </span>
          <div className="meta-chip-stack">
            <span className="meta-chip">
              {t('overview.currentDevice')}: {activeDevice?.name ?? t('common.none')}
            </span>
            <span className="meta-chip">
              {t('overview.lastAttempt')}: {state.connection.lastAttemptAt ?? t('common.notAvailable')}
            </span>
            <span className="meta-chip">
              {t('overview.lastTrigger')}: {state.connection.lastTrigger ?? t('common.notAvailable')}
            </span>
          </div>
        </div>
      </article>

      <article className="surface-card feature-note cockpit-health-card">
        <div className="feature-note-header">
          <span className="feature-note-icon" aria-hidden="true">
            {sourceAvailability === 'available' ? 'OK' : '!'}
          </span>
          <div>
            <h3>{t(`cockpit.health.${sourceAvailability}.title`)}</h3>
            <p className="feature-note-copy">
              {t(`cockpit.health.${sourceAvailability}.description`)}
            </p>
          </div>
        </div>
        <div className="feature-note-tags">
          <span className="feature-note-tag">
            {t('a2dp.debug.bridgeMode')}: {state.runtime.bridgeMode}
          </span>
          <span className="feature-note-tag">
            {t('a2dp.debug.matchedSources')}: {state.devices.filter((device) => device.supportsAudio).length}
          </span>
        </div>
        <button type="button" className="secondary-button" onClick={onOpenDiagnostics}>
          {t('cockpit.openDiagnostics')}
        </button>
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('overview.recentActivity')}</h3>
          <span className="status-pill subtle">{state.recentActivity.length}</span>
        </div>
        {state.recentActivity.length === 0 ? (
          <p className="muted">{t('overview.noActivity')}</p>
        ) : (
          <ul className="timeline-list">
            {state.recentActivity.map((item) => (
              <li key={item.id} className={`activity-item ${item.level}`}>
                <div className="activity-head">
                  <strong>{item.title}</strong>
                  <span className="muted">{item.happenedAt || t('common.notAvailable')}</span>
                </div>
                {item.detail ? <p className="activity-detail">{item.detail}</p> : null}
                {(item.area || item.deviceId || item.errorCode) ? (
                  <div className="activity-meta">
                    <span>{t('overview.activity.area', { value: item.area })}</span>
                    {item.deviceId ? (
                      <span>{t('overview.activity.device', { value: item.deviceId })}</span>
                    ) : null}
                    {item.errorCode ? (
                      <span>{t('overview.activity.code', { value: item.errorCode })}</span>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </article>

      <article className="surface-card compact-card cockpit-latest-card">
        <div className="card-head">
          <h3>{t('cockpit.recoveryTitle')}</h3>
          <span className="status-pill subtle">
            {state.connection.lastErrorMessage ? t('overview.status.failed') : t('common.on')}
          </span>
        </div>
        {state.connection.lastErrorMessage ? (
          <>
            <p className="feature-note-copy">
              {t('overview.lastFailure', { message: state.connection.lastErrorMessage })}
            </p>
            {state.connection.lastErrorCode ? (
              <p className="muted">
                {t('overview.lastErrorCode', { value: state.connection.lastErrorCode })}
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted">{t('overview.noFailure')}</p>
        )}
      </article>
    </section>
  )
}
