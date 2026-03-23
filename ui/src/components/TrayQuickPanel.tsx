import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode, DeviceViewModel } from '../types'
import { A2dpSourceStatus } from './A2dpSourceStatus'

interface TrayQuickPanelProps {
  currentDevice?: DeviceViewModel
  autoConnectEnabled: boolean
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleAutoConnect: (enabled: boolean) => void
  onOpenBluetoothSettings: () => void
  onRefreshDevices: () => void
}

export function TrayQuickPanel({
  currentDevice,
  autoConnectEnabled,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  onConnect,
  onDisconnect,
  onToggleAutoConnect,
  onOpenBluetoothSettings,
  onRefreshDevices,
}: TrayQuickPanelProps) {
  const { t } = useI18n()
  const targetDevice = currentDevice ?? matchedSourceDevices[0]
  const hasTargetDevice = Boolean(targetDevice)

  return (
    <section className="surface-card tray-quick-panel" aria-label="Tray quick panel">
      <div className="tray-quick-panel-header">
        <div>
          <p className="panel-kicker">{t('tray.title')}</p>
          <h3>
            {currentDevice
              ? currentDevice.name
              : targetDevice
                ? targetDevice.name
                : t('tray.noActiveDevice')}
          </h3>
          <p className="muted">
            {currentDevice
              ? t('tray.connectedTo', { name: currentDevice.name })
              : t('tray.noActiveDevice')}
          </p>
        </div>
        <span className="status-pill subtle">
          {currentDevice?.isConnected
            ? t('device.status.connected')
            : hasTargetDevice
              ? t('device.status.available')
              : t('common.none')}
        </span>
      </div>

      <div className="tray-actions">
        {currentDevice?.isConnected ? (
          <button
            type="button"
            className="primary-button"
            onClick={() => onDisconnect(currentDevice.id)}
          >
            {t('device.action.disconnect')}
          </button>
        ) : targetDevice ? (
          <button
            type="button"
            className="primary-button"
            onClick={() => onConnect(targetDevice.id)}
          >
            {t('device.action.connect')}
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={onRefreshDevices}>
          {t('command.refreshDevices')}
        </button>
        <button type="button" className="secondary-button" onClick={onOpenBluetoothSettings}>
          {t('tray.openBluetoothSettings')}
        </button>
      </div>

      <div className="tray-quick-panel-footer">
        <label className="toggle-row compact">
          <span>{t('tray.autoConnect')}</span>
          <input
            type="checkbox"
            checked={autoConnectEnabled}
            disabled={!matchedSourceDevices.length}
            onChange={(event) => onToggleAutoConnect(event.target.checked)}
          />
        </label>
      </div>

      <A2dpSourceStatus
        mode="compact"
        availability={sourceAvailability}
        bridgeMode={bridgeMode}
        totalDevices={totalDevices}
        matchedSourceDevices={matchedSourceDevices}
        debugDevices={debugDevices}
      />
    </section>
  )
}
