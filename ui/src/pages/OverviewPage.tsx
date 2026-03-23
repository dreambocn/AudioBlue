import { A2dpSourceStatus } from '../components/A2dpSourceStatus'
import { useI18n } from '../i18n'
import type {
  A2dpSourceAvailability,
  AppState,
  BridgeMode,
  DeviceViewModel,
} from '../types'

interface OverviewPageProps {
  state: AppState
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
}

export function OverviewPage({
  state,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
}: OverviewPageProps) {
  const { t } = useI18n()
  const connectedDevice =
    state.devices.find(
      (device) =>
        device.id === state.connection.currentDeviceId &&
        device.isConnected,
    ) ?? state.devices.find((device) => device.isConnected)

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>{t('overview.title')}</h2>
        <p className="status-pill">
          {t('overview.currentDevice')}: {connectedDevice ? connectedDevice.name : t('common.none')}
        </p>
        {state.connection.lastFailure ? (
          <p className="muted">
            {t('overview.lastFailure', { message: state.connection.lastFailure })}
          </p>
        ) : (
          <p className="muted">{t('overview.noFailure')}</p>
        )}
      </article>

      <article className="surface-card">
        <h3>{t('overview.recentActivity')}</h3>
        <ul className="compact-list">
          {state.recentActivity.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>

      <A2dpSourceStatus
        availability={sourceAvailability}
        bridgeMode={bridgeMode}
        totalDevices={totalDevices}
        matchedSourceDevices={matchedSourceDevices}
        debugDevices={debugDevices}
      />
    </section>
  )
}
