import type { AppState, NotificationPolicy, ThemeMode } from '../types'

interface SettingsPageProps {
  state: AppState
  onThemeChange: (theme: ThemeMode) => void
  onAutostartChange: (enabled: boolean) => void
  onNotificationPolicyChange: (policy: NotificationPolicy) => void
  onExportDiagnostics: () => void
}

export function SettingsPage({
  state,
  onThemeChange,
  onAutostartChange,
  onNotificationPolicyChange,
  onExportDiagnostics,
}: SettingsPageProps) {
  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>Settings</h2>
        <div className="settings-grid">
          <label className="field-row">
            <span>Theme mode</span>
            <select
              aria-label="Theme mode"
              value={state.ui.themeMode}
              onChange={(event) => onThemeChange(event.target.value as ThemeMode)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>

          <label className="toggle-row">
            <span>Start with Windows</span>
            <input
              type="checkbox"
              checked={state.startup.autostart}
              onChange={(event) => onAutostartChange(event.target.checked)}
            />
          </label>

          <label className="field-row">
            <span>Notification policy</span>
            <select
              value={state.notifications.policy}
              onChange={(event) =>
                onNotificationPolicyChange(event.target.value as NotificationPolicy)
              }
            >
              <option value="silent">Silent</option>
              <option value="failures">Only failures</option>
              <option value="all">All notifications</option>
            </select>
          </label>
        </div>
      </article>

      <article className="surface-card">
        <h3>Diagnostics</h3>
        <p className="muted">{state.diagnostics.lastProbe}</p>
        <p className="muted">{state.diagnostics.probeResult}</p>
        <button type="button" className="secondary-button" onClick={onExportDiagnostics}>
          Export diagnostics
        </button>
        {state.diagnostics.lastExportPath ? (
          <p className="muted">Exported to: {state.diagnostics.lastExportPath}</p>
        ) : null}
      </article>

      <article className="surface-card">
        <h3>Updates</h3>
        <p className="muted">Check for updates is reserved for the installer channel.</p>
        <button type="button" className="secondary-button" disabled>
          Check for updates (coming soon)
        </button>
      </article>
    </section>
  )
}
