import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode, DeviceViewModel } from '../types'
import { A2dpSourceStatus } from './A2dpSourceStatus'

interface TrayQuickPanelProps {
  currentDevice?: DeviceViewModel
  reconnectOnNextStart: boolean
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onConnect: (deviceId: string) => void
  onDisconnect: (deviceId: string) => void
  onToggleReconnect: (enabled: boolean) => void
  onOpenBluetoothSettings: () => void
  onRefreshDevices: () => void
}

export function TrayQuickPanel({
  currentDevice,
  reconnectOnNextStart,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  onConnect,
  onDisconnect,
  onToggleReconnect,
  onOpenBluetoothSettings,
  onRefreshDevices,
}: TrayQuickPanelProps) {
  const { t } = useI18n()
  // 优先展示当前已连接设备；若尚未连接，则退化为第一个可操作的音频源设备。
  const targetDevice = currentDevice ?? matchedSourceDevices[0]
  const hasTargetDevice = Boolean(targetDevice)
  const panelTitle = currentDevice
    ? currentDevice.name
    : targetDevice
      ? targetDevice.name
      : t('tray.noActiveDevice')
  const panelSubtitle = currentDevice
    ? t('tray.connectedTo', { name: currentDevice.name })
    : t('tray.noActiveDevice')

  return (
    <section className="surface-card tray-quick-panel" aria-label="Tray quick panel">
      <div className="tray-quick-panel-header">
        <div className="tray-quick-panel-copy">
          <p className="panel-kicker">{t('tray.title')}</p>
          <h3 className="text-truncate" data-testid="tray-quick-panel-title" title={panelTitle}>
            {panelTitle}
          </h3>
          <p className="muted text-truncate" title={panelSubtitle}>
            {panelSubtitle}
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

      {/* 快捷区只暴露最常用操作，避免托盘场景下信息过载。 */}
      <div className="tray-actions" data-testid="tray-action-row">
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

      {/* 这里切换的是“下次启动时重连”偏好，而不是立即重连。 */}
      <div className="tray-preference-bar">
        <span className="tray-preference-label">{t('tray.startupPreference')}</span>
        <button
          type="button"
          className={`secondary-button state-pill-button ${reconnectOnNextStart ? 'is-active' : ''}`}
          aria-pressed={reconnectOnNextStart}
          onClick={() => onToggleReconnect(!reconnectOnNextStart)}
        >
          {t('tray.reconnectOnNextStartState', {
            state: reconnectOnNextStart ? t('common.on') : t('common.off'),
          })}
        </button>
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
