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
  onOpenControlCenter: () => void
  onOpenBluetoothSettings: () => void
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
  onOpenControlCenter,
  onOpenBluetoothSettings,
}: TrayQuickPanelProps) {
  const { t } = useI18n()

  return (
    <section className="surface-card tray-quick-panel" aria-label="Tray quick panel">
      <h3>{t('tray.title')}</h3>
      <p className="muted">
        {currentDevice
          ? t('tray.connectedTo', { name: currentDevice.name })
          : t('tray.noActiveDevice')}
      </p>
      <div className="tray-actions">
        {currentDevice?.isConnected ? (
          <button type="button" className="secondary-button" onClick={() => onDisconnect(currentDevice.id)}>
            {t('device.action.disconnect')}
          </button>
        ) : currentDevice ? (
          <button type="button" className="primary-button" onClick={() => onConnect(currentDevice.id)}>
            {t('device.action.connect')}
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={onOpenControlCenter}>
          {t('tray.openControlCenter')}
        </button>
        <button type="button" className="secondary-button" onClick={onOpenBluetoothSettings}>
          {t('tray.openBluetoothSettings')}
        </button>
      </div>
      <label className="toggle-row">
        <span>{t('tray.autoConnect')}</span>
        <input
          type="checkbox"
          checked={autoConnectEnabled}
          onChange={(event) => onToggleAutoConnect(event.target.checked)}
        />
      </label>
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
