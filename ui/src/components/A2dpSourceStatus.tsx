import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode, DeviceViewModel } from '../types'

interface A2dpSourceStatusProps {
  availability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  mode?: 'compact' | 'detailed'
}

const getTitleKey = (availability: A2dpSourceAvailability) => {
  if (availability === 'unavailable') {
    return 'a2dp.unavailable.title'
  }
  if (availability === 'no-source') {
    return 'a2dp.noSource.title'
  }
  return 'a2dp.available.title'
}

const getDescriptionKey = (availability: A2dpSourceAvailability) => {
  if (availability === 'unavailable') {
    return 'a2dp.unavailable.description'
  }
  if (availability === 'no-source') {
    return 'a2dp.noSource.description'
  }
  return 'a2dp.available.description'
}

export function A2dpSourceStatus({
  availability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  mode = 'detailed',
}: A2dpSourceStatusProps) {
  const { t } = useI18n()
  const previewDevices = debugDevices.slice(0, 3)
  const recentSeen =
    matchedSourceDevices[0]?.lastSeen ?? debugDevices[0]?.lastSeen ?? t('common.unknown')

  if (mode === 'compact') {
    return (
      <article
        className="a2dp-status-card a2dp-status-card-compact"
        data-testid="a2dp-source-status-compact"
      >
        <div className="a2dp-status-header">
          <div>
            <h3>{t(getTitleKey(availability))}</h3>
            <p className="muted">{t(getDescriptionKey(availability))}</p>
          </div>
          <span className="status-pill subtle">
            {t('a2dp.debug.matchedSources')}: {matchedSourceDevices.length}
          </span>
        </div>

        <div className="meta-chip-row">
          <span className="meta-chip">
            {t('a2dp.debug.bridgeMode')}: {bridgeMode}
          </span>
          <span className="meta-chip">
            {t('a2dp.debug.totalDevices')}: {totalDevices}
          </span>
          <span className="meta-chip">
            {t('a2dp.debug.lastSeen')}: {recentSeen}
          </span>
        </div>
      </article>
    )
  }

  return (
    <article
      className="surface-card a2dp-status-card a2dp-status-card-detailed"
      data-testid="a2dp-source-status-detailed"
    >
      <div className="a2dp-status-header">
        <div>
          <h3>{t(getTitleKey(availability))}</h3>
          <p className="muted">{t(getDescriptionKey(availability))}</p>
        </div>
      </div>
      <div className="a2dp-detail-grid">
        <p className="muted">
          {t('a2dp.debug.bridgeMode')}: {bridgeMode}
        </p>
        <p className="muted">
          {t('a2dp.debug.totalDevices')}: {totalDevices}
        </p>
        <p className="muted">
          {t('a2dp.debug.matchedSources')}: {matchedSourceDevices.length}
        </p>
      </div>
      <div className="a2dp-debug-list">
        {previewDevices.map((device) => (
          <p key={device.id} className="muted">
            {t('a2dp.debug.deviceId')}: {device.id} · {t('a2dp.debug.lastSeen')}:{' '}
            {device.lastSeen}
          </p>
        ))}
      </div>
    </article>
  )
}
