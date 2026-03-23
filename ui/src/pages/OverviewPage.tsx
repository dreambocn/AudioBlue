import { useI18n } from '../i18n'
import type { AppState } from '../types'

interface OverviewPageProps {
  state: AppState
}

export function OverviewPage({ state }: OverviewPageProps) {
  const { t } = useI18n()
  const connectedDevice =
    state.devices.find(
      (device) =>
        device.id === state.connection.currentDeviceId &&
        device.isConnected,
    ) ?? state.devices.find((device) => device.isConnected)

  return (
    <section className="page-grid overview-grid">
      <article className="surface-card spotlight-card">
        <div className="card-head">
          <h3>{t('overview.title')}</h3>
          <span className="status-pill">
            {t('overview.currentDevice')}: {connectedDevice ? connectedDevice.name : t('common.none')}
          </span>
        </div>
        {state.connection.lastFailure ? (
          <p className="muted">
            {t('overview.lastFailure', { message: state.connection.lastFailure })}
          </p>
        ) : (
          <p className="muted">{t('overview.noFailure')}</p>
        )}
      </article>

      <article className="surface-card compact-card">
        <h3>{t('overview.recentActivity')}</h3>
        <ul className="compact-list">
          {state.recentActivity.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
    </section>
  )
}
