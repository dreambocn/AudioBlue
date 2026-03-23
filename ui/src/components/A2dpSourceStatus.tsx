import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode, DeviceViewModel } from '../types'

interface A2dpSourceStatusProps {
  availability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
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
}: A2dpSourceStatusProps) {
  const { t } = useI18n()
  const previewDevices = debugDevices.slice(0, 2)

  return (
    <article className="surface-card a2dp-status-card" data-testid="a2dp-source-status">
      <h3>{t(getTitleKey(availability))}</h3>
      <p className="muted">{t(getDescriptionKey(availability))}</p>
      <p className="muted">
        {t('a2dp.debug.bridgeMode')}: {bridgeMode}
      </p>
      <p className="muted">
        {t('a2dp.debug.totalDevices')}: {totalDevices}
      </p>
      <p className="muted">
        {t('a2dp.debug.matchedSources')}: {matchedSourceDevices.length}
      </p>
      {previewDevices.map((device) => (
        <p key={device.id} className="muted">
          {t('a2dp.debug.deviceId')}: {device.id} · {t('a2dp.debug.lastSeen')}:{' '}
          {device.lastSeen}
        </p>
      ))}
    </article>
  )
}
