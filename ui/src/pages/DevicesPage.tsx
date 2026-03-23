import { A2dpSourceStatus } from '../components/A2dpSourceStatus'
import { DeviceCard } from '../components/DeviceCard'
import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode, DeviceViewModel } from '../types'

interface DevicesPageProps {
  devices: DeviceViewModel[]
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => void
}

export function DevicesPage({
  devices,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  onConnect,
  onDisconnect,
  onToggleFavorite,
}: DevicesPageProps) {
  const { t } = useI18n()

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>{t('devices.title')}</h2>
        <p className="muted">{t('devices.description')}</p>
      </article>

      <A2dpSourceStatus
        availability={sourceAvailability}
        bridgeMode={bridgeMode}
        totalDevices={totalDevices}
        matchedSourceDevices={matchedSourceDevices}
        debugDevices={debugDevices}
      />

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
