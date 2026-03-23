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
  const visibleDeviceIds = new Set(devices.map((device) => device.id))
  const historyItems = deviceHistory.filter((entry) => !visibleDeviceIds.has(entry.id))

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

  const resolveHistoryResult = (entry: DeviceHistoryEntry) => {
    if (entry.lastConnectionState === 'connected') {
      return t('device.status.connected')
    }
    return entry.lastResult
  }

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
          <span className="status-pill subtle">{t('devices.history.status.offline')}</span>
        </div>
        <p className="muted">{t('devices.history.description')}</p>
      </article>

      <div className="device-history-grid">
        {historyItems.length === 0 ? (
          <article className="surface-card compact-card">
            <p className="muted">{t('devices.history.empty')}</p>
          </article>
        ) : (
          historyItems.map((entry) => (
            <article key={entry.id} className="surface-card history-card">
              <div className="card-head">
                <div>
                  <h3>{entry.name}</h3>
                  <p className="muted">
                    {t('device.lastResult', { value: resolveHistoryResult(entry) })}
                  </p>
                </div>
                <span className="status-pill subtle">{t('devices.history.status.offline')}</span>
              </div>
              <div className="history-meta-row">
                {entry.lastConnectionAt ? (
                  <span className="meta-chip">
                    {t('devices.history.lastConnection', { value: entry.lastConnectionAt })}
                  </span>
                ) : null}
                <span className="meta-chip">
                  {t('devices.history.lastSeen', { value: entry.lastSeen })}
                </span>
              </div>
              <div className="history-tag-row">{renderHistoryTags(entry)}</div>
              <p className="muted history-footnote">{t('devices.history.reuse')}</p>
            </article>
          ))
        )}
      </div>
    </section>
  )
}
