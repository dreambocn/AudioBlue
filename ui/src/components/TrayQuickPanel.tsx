import type { DeviceViewModel } from '../types'

interface TrayQuickPanelProps {
  currentDevice?: DeviceViewModel
  autoConnectEnabled: boolean
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleAutoConnect: (enabled: boolean) => void
  onOpenControlCenter: () => void
  onOpenBluetoothSettings: () => void
}

export function TrayQuickPanel({
  currentDevice,
  autoConnectEnabled,
  onConnect,
  onDisconnect,
  onToggleAutoConnect,
  onOpenControlCenter,
  onOpenBluetoothSettings,
}: TrayQuickPanelProps) {
  return (
    <section className="surface-card tray-quick-panel" aria-label="Tray quick panel">
      <h3>Quick Actions</h3>
      <p className="muted">
        {currentDevice ? `Connected to ${currentDevice.name}` : 'No active audio device'}
      </p>
      <div className="tray-actions">
        {currentDevice?.isConnected ? (
          <button type="button" className="secondary-button" onClick={() => onDisconnect(currentDevice.id)}>
            Disconnect
          </button>
        ) : currentDevice ? (
          <button type="button" className="primary-button" onClick={() => onConnect(currentDevice.id)}>
            Connect
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={onOpenControlCenter}>
          Open Control Center
        </button>
        <button type="button" className="secondary-button" onClick={onOpenBluetoothSettings}>
          Open Bluetooth Settings
        </button>
      </div>
      <label className="toggle-row">
        <span>Auto-connect</span>
        <input
          type="checkbox"
          checked={autoConnectEnabled}
          onChange={(event) => onToggleAutoConnect(event.target.checked)}
        />
      </label>
    </section>
  )
}
