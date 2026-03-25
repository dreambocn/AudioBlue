import { DeviceCard } from '../components/DeviceCard'
import { useI18n } from '../i18n'
import type { DeviceHistoryEntry, DeviceViewModel } from '../types'

interface DevicesPageProps {
  devices: DeviceViewModel[]
  deviceHistory: DeviceHistoryEntry[]
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => void
}

export function DevicesPage({
  devices,
  deviceHistory = [],
  onConnect,
  onDisconnect,
  onToggleFavorite,
}: DevicesPageProps) {
  const { t } = useI18n()

  const renderHistoryTags = (entry: DeviceHistoryEntry) => {
    const tags: string[] = []
    if (entry.savedRule.isFavorite) {
      tags.push(t('devices.history.tag.favorite'))
    }
    if (entry.savedRule.isIgnored) {
      tags.push(t('devices.history.tag.ignored'))
    }
    if (entry.savedRule.autoConnectOnAppear) {
      tags.push(t('devices.history.tag.reappear'))
    }
    if (typeof entry.savedRule.priority === 'number') {
      tags.push(t('devices.history.tag.priority', { value: entry.savedRule.priority }))
    }

    if (tags.length === 0) {
      tags.push(t('devices.history.tag.none'))
    }

    return tags.map((tag) => (
      <span key={`${entry.id}-${tag}`} className="history-tag">
        {tag}
      </span>
    ))
  }

  const resolveHistoryStatus = (entry: DeviceHistoryEntry) =>
    entry.isCurrentlyVisible
      ? t('devices.history.status.online')
      : t('devices.history.status.offline')

  return (
    <section className="page-grid">
      <article className="surface-card compact-card">
        <h3>{t('devices.title')}</h3>
        <p className="muted">{t('devices.description')}</p>
      </article>

      <div className="device-grid">
        {devices.length === 0 ? (
          <article className="surface-card">
            <p className="muted">{t('devices.empty')}</p>
          </article>
        ) : (
          devices.map((device) => (
            <DeviceCard
              key={device.id}
              device={device}
              onConnect={onConnect}
              onDisconnect={onDisconnect}
              onToggleFavorite={onToggleFavorite}
            />
          ))
        )}
      </div>

      <article className="surface-card compact-card">
        <div className="card-head">
          <h3>{t('devices.history.title')}</h3>
          <span className="status-pill subtle">{deviceHistory.length}</span>
        </div>
        <p className="muted">{t('devices.history.description')}</p>
      </article>

      <div className="device-history-grid">
        {deviceHistory.length === 0 ? (
          <article className="surface-card compact-card">
            <p className="muted">{t('devices.history.empty')}</p>
          </article>
        ) : (
          deviceHistory.map((entry) => (
            <article key={entry.id} className="surface-card history-card">
              <div className="card-head">
                <div>
                  <h3>{entry.name}</h3>
                  <p className="muted">
                    {t('device.lastResult', { value: entry.lastResult })}
                  </p>
                </div>
                <span className={`status-pill subtle ${entry.isCurrentlyVisible ? 'connected' : ''}`}>
                  {resolveHistoryStatus(entry)}
                </span>
              </div>
              <div className="history-meta-row">
                <span className="meta-chip">
                  {t('devices.history.successCount', { value: entry.successCount })}
                </span>
                <span className="meta-chip">
                  {t('devices.history.failureCount', { value: entry.failureCount })}
                </span>
                {entry.lastSuccessAt ? (
                  <span className="meta-chip">
                    {t('devices.history.lastSuccess', { value: entry.lastSuccessAt })}
                  </span>
                ) : null}
                {entry.lastFailureAt ? (
                  <span className="meta-chip">
                    {t('devices.history.lastFailure', { value: entry.lastFailureAt })}
                  </span>
                ) : null}
              </div>
              <div className="history-tag-row">{renderHistoryTags(entry)}</div>
              <details className="diagnostics-details">
                <summary>{t('devices.history.technicalDetails')}</summary>
                <div className="diagnostics-details-content">
                  <div className="details-list">
                    <p>{t('devices.history.firstSeen', { value: entry.firstSeen ?? t('common.notAvailable') })}</p>
                    <p>{t('devices.history.lastSeen', { value: entry.lastSeen })}</p>
                    <p>
                      {t('devices.history.lastConnection', {
                        value: entry.lastConnectionAt ?? t('common.notAvailable'),
                      })}
                    </p>
                    <p>
                      {t('devices.history.lastPresent', {
                        value: entry.lastPresentAt ?? t('common.notAvailable'),
                      })}
                    </p>
                    <p>
                      {t('devices.history.lastAbsent', {
                        value: entry.lastAbsentAt ?? t('common.notAvailable'),
                      })}
                    </p>
                    {entry.lastErrorCode ? (
                      <p>{t('overview.activity.code', { value: entry.lastErrorCode })}</p>
                    ) : null}
                    {entry.lastPresentReason ? (
                      <p>{t('devices.history.reason', { value: entry.lastPresentReason })}</p>
                    ) : null}
                    {entry.lastAbsentReason ? (
                      <p>{t('devices.history.reason', { value: entry.lastAbsentReason })}</p>
                    ) : null}
                  </div>
                </div>
              </details>
            </article>
          ))
        )}
      </div>
    </section>
  )
}
