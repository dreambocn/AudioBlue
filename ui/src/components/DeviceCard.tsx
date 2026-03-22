import type { DeviceViewModel } from '../types'

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
  const statusLabel = device.isConnected
    ? 'Connected'
    : device.isConnecting
      ? 'Connecting…'
      : 'Available'

  return (
    <article className="surface-card device-card">
      <header className="device-card-header">
        <h3>{device.name}</h3>
        <button
          type="button"
          className="chip-button"
          aria-label={`${device.isFavorite ? 'Remove' : 'Add'} ${device.name} ${device.isFavorite ? 'from' : 'to'} favorites`}
          onClick={() => onToggleFavorite(device.id, !device.isFavorite)}
        >
          {device.isFavorite ? '★ Favorite' : '☆ Favorite'}
        </button>
      </header>

      <p className="muted">{statusLabel}</p>
      <p className="muted">Last seen: {device.lastSeen}</p>
      <p className="muted">Last result: {device.lastResult}</p>

      <div className="device-card-actions">
        {device.isConnected ? (
          <button type="button" className="secondary-button" onClick={() => onDisconnect(device.id)}>
            Disconnect
          </button>
        ) : (
          <button type="button" className="primary-button" onClick={() => onConnect(device.id)}>
            Connect
          </button>
        )}
      </div>
    </article>
  )
}
