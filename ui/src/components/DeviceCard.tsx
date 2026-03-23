import type { DeviceViewModel } from '../types'
import { useI18n } from '../i18n'

interface DeviceCardProps {
  device: DeviceViewModel
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => void
}

export function DeviceCard({
  device,
  onConnect,
  onDisconnect,
  onToggleFavorite,
}: DeviceCardProps) {
  const { t } = useI18n()
  const statusLabel = device.isConnected
    ? t('device.status.connected')
    : device.isConnecting
      ? t('device.status.connecting')
      : t('device.status.available')

  return (
    <article className="surface-card device-card">
      <header className="device-card-header">
        <h3>{device.name}</h3>
        <button
          type="button"
          className="chip-button"
          aria-label={
            device.isFavorite
              ? t('device.favorite.remove', { name: device.name })
              : t('device.favorite.add', { name: device.name })
          }
          onClick={() => onToggleFavorite(device.id, !device.isFavorite)}
        >
          {device.isFavorite ? t('device.favorite.on') : t('device.favorite.off')}
        </button>
      </header>

      <p className="muted">{statusLabel}</p>
      {device.isConnected && !device.presentInLastScan ? (
        <p className="muted">{t('devices.retainedHint')}</p>
      ) : null}
      <p className="muted">{t('device.lastSeen', { value: device.lastSeen })}</p>
      <p className="muted">{t('device.lastResult', { value: device.lastResult })}</p>

      <div className="device-card-actions">
        {device.isConnected ? (
          <button type="button" className="secondary-button" onClick={() => onDisconnect(device.id)}>
            {t('device.action.disconnect')}
          </button>
        ) : (
          <button type="button" className="primary-button" onClick={() => onConnect(device.id)}>
            {t('device.action.connect')}
          </button>
        )}
      </div>
    </article>
  )
}
