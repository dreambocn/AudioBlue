import { useI18n } from '../i18n'
import type { AppState } from '../types'

interface OverviewPageProps {
  state: AppState
}

export function OverviewPage({ state }: OverviewPageProps) {
  const { t } = useI18n()
  // 摘要区优先命中当前连接设备 id，旧快照缺失时再回退到任意已连接设备。
  const connectedDevice =
    state.devices.find(
      (device) =>
        device.id === state.connection.currentDeviceId &&
        device.isConnected,
    ) ?? state.devices.find((device) => device.isConnected)

  return (
    <section className="page-grid overview-grid">
      <article className="surface-card spotlight-card">
        <div className="card-head">
          <h3>{t('overview.title')}</h3>
          <span className={`status-pill ${state.connection.status}`}>
            {t(`overview.status.${state.connection.currentPhase ?? state.connection.status}`)}
          </span>
        </div>
        <div className="overview-summary-grid">
          <div className="meta-chip">
            {t('overview.currentDevice')}: {connectedDevice ? connectedDevice.name : t('common.none')}
          </div>
          <div className="meta-chip">
            {t('overview.lastSuccess')}: {state.connection.lastSuccessAt ?? t('common.notAvailable')}
          </div>
          <div className="meta-chip">
            {t('overview.lastAttempt')}: {state.connection.lastAttemptAt ?? t('common.notAvailable')}
          </div>
          <div className="meta-chip">
            {t('overview.lastTrigger')}: {state.connection.lastTrigger ?? t('common.notAvailable')}
          </div>
        </div>
        {state.connection.lastErrorMessage ? (
          <div className="feature-note feature-note-subtle">
            <div className="feature-note-header">
              <span className="feature-note-icon" aria-hidden="true">
                !
              </span>
              <p className="feature-note-copy">
                {t('overview.lastFailure', { message: state.connection.lastErrorMessage })}
              </p>
            </div>
            {state.connection.lastErrorCode ? (
              <p className="muted">
                {t('overview.lastErrorCode', { value: state.connection.lastErrorCode })}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="muted">{t('overview.noFailure')}</p>
        )}
      </article>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('overview.recentActivity')}</h3>
          <span className="status-pill subtle">{state.recentActivity.length}</span>
        </div>
        {/* 活动流同时保留用户可读文案与诊断字段，方便界面查看和问题排查。 */}
        {state.recentActivity.length === 0 ? (
          <p className="muted">{t('overview.noActivity')}</p>
        ) : (
          <ul className="timeline-list">
            {state.recentActivity.map((item) => (
              <li key={item.id} className={`activity-item ${item.level}`}>
                <div className="activity-head">
                  <strong>{item.title}</strong>
                  <span className="muted">
                    {item.happenedAt || t('common.notAvailable')}
                  </span>
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
    </section>
  )
}
