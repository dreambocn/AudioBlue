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
  // 卡片优先体现设备的实时连接状态，其次再回落到“可连接”状态。
  const statusLabel = device.isConnected
    ? t('device.status.connected')
    : device.isConnecting
      ? t('device.status.connecting')
      : t('device.status.available')

  return (
    <article className="surface-card device-card">
      <header className="device-card-header">
        <h3 className="text-truncate" title={device.name}>
          {device.name}
        </h3>
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
      {/* 设备已连接但本轮扫描未命中时，提示这是保留连接态而非最新枚举结果。 */}
      {device.isConnected && !device.presentInLastScan ? (
        <p className="muted">{t('devices.retainedHint')}</p>
      ) : null}
      <p className="muted">{t('device.lastSeen', { value: device.lastSeen })}</p>
      <p className="muted text-wrap-anywhere">{t('device.lastResult', { value: device.lastResult })}</p>

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
