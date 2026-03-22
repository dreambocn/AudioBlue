import type { DeviceViewModel } from '../types'

interface AutomationPageProps {
  devices: DeviceViewModel[]
  onToggleAppearRule: (deviceId: string, enabled: boolean) => void
}

export function AutomationPage({ devices, onToggleAppearRule }: AutomationPageProps) {
  const primaryDevice = devices[0]

  if (!primaryDevice) {
    return (
      <section className="surface-card">
        <h2>Automation</h2>
        <p className="muted">No devices discovered yet.</p>
      </section>
    )
  }

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>Automation Rules</h2>
        <p className="muted">Configure trigger strategy and fallback order.</p>
        <label className="toggle-row">
          <span>Auto-connect when this device appears</span>
          <input
            type="checkbox"
            aria-label="Auto-connect when this device appears"
            checked={primaryDevice.rule.autoConnectOnAppear}
            onChange={(event) =>
              onToggleAppearRule(primaryDevice.id, event.target.checked)
            }
          />
        </label>
      </article>

      <article className="surface-card">
        <h3>Priority Queue</h3>
        <ol className="compact-list">
          {devices.map((device) => (
            <li key={device.id}>
              {device.name} {device.isIgnored ? '(Ignored)' : ''}
            </li>
          ))}
        </ol>
      </article>
    </section>
  )
}
