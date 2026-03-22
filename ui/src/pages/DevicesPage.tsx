import { DeviceCard } from '../components/DeviceCard'
import { useI18n } from '../i18n'
import type { DeviceViewModel } from '../types'

interface DevicesPageProps {
  devices: DeviceViewModel[]
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => void
}

export function DevicesPage({
  devices,
  onConnect,
  onDisconnect,
  onToggleFavorite,
}: DevicesPageProps) {
  const { t } = useI18n()

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>Audio Devices</h2>
        <p className="muted">Manage favorites, status and quick connection actions.</p>
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
    </section>
  )
}
