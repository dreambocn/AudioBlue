import type { AppState } from '../types'
import { useI18n } from '../i18n'

interface OverviewPageProps {
  state: AppState
}

export function OverviewPage({ state }: OverviewPageProps) {
  const { t } = useI18n()
  const connectedDevice =
    state.devices.find(
      (device) =>
        device.id === state.connection.currentDeviceId &&
        device.isConnected &&
        device.supportsAudio,
    ) ?? state.devices.find((device) => device.isConnected && device.supportsAudio)

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>Connection Overview</h2>
        <p className="status-pill">
          {t('overview.currentDevice')}: {connectedDevice ? connectedDevice.name : t('common.none')}
        </p>
        {state.connection.lastFailure ? (
          <p className="muted">Last failure: {state.connection.lastFailure}</p>
        ) : (
          <p className="muted">No recent failures</p>
        )}
      </article>

      <article className="surface-card">
        <h3>Recent Activity</h3>
        <ul className="compact-list">
          {state.recentActivity.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
    </section>
  )
}
