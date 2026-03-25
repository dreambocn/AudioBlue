import { useEffect, useState } from 'react'
import type { BackendBridge } from '../bridge/types'
import { useResolvedBridge } from '../bridge/useResolvedBridge'
import { TrayQuickPanel } from '../components/TrayQuickPanel'
import { LanguageProvider } from '../i18n'
import type { AppState } from '../types'

interface TrayQuickPanelViewProps {
  bridge?: BackendBridge
}

export function TrayQuickPanelView({ bridge }: TrayQuickPanelViewProps) {
  const resolvedBridge = useResolvedBridge(bridge)
  const [state, setState] = useState<AppState | null>(null)

  useEffect(() => {
    // 订阅桥接事件，并把增量更新折叠进本地状态，保持托盘快速面板与主界面一致。
    let alive = true
    resolvedBridge.getInitialState().then((initial) => {
      if (alive) {
        setState(initial)
      }
    })

    const unsub = resolvedBridge.onEvent((event) => {
      // 托盘面板只同步自己会展示的字段，避免复用整套控制中心状态机。
      if (event.type === 'devices_changed') {
        setState((current) => (current ? { ...current, devices: event.devices } : current))
      }
      if (event.type === 'history_changed') {
        setState((current) =>
          current ? { ...current, deviceHistory: event.deviceHistory } : current,
        )
      }
      if (event.type === 'connection_changed') {
        setState((current) =>
          current ? { ...current, connection: event.connection } : current,
        )
      }
      if (event.type === 'settings_changed') {
        setState((current) =>
          current
            ? {
                ...current,
                startup: event.settings.startup,
                ui: event.settings.ui,
                notifications: event.settings.notifications,
              }
            : current,
        )
      }
    })

    return () => {
      alive = false
      unsub()
    }
  }, [resolvedBridge])

  if (!state) {
    return <div className="loading-shell">Loading quick panel…</div>
  }

  // 托盘视图沿用主界面的音频源判定规则，避免两边提示口径不一致。
  const activeDevice = state.devices.find(
    (device) => device.id === state.connection.currentDeviceId,
  )
  const audioDevices = state.devices.filter((device) => device.supportsAudio)
  // 快速面板只关心三种状态：桥接不可用、暂无音频源、已有可操作设备。
  const sourceAvailability =
    state.runtime.bridgeMode === 'unavailable'
      ? 'unavailable'
      : audioDevices.length === 0
        ? 'no-source'
        : 'available'

  return (
    <LanguageProvider preference={state.ui.language}>
      <TrayQuickPanel
        currentDevice={activeDevice}
        reconnectOnNextStart={state.startup.reconnectOnNextStart}
        sourceAvailability={sourceAvailability}
        bridgeMode={state.runtime.bridgeMode}
        totalDevices={state.devices.length}
        matchedSourceDevices={audioDevices}
        debugDevices={state.devices}
        onConnect={(id) => resolvedBridge.connectDevice(id)}
        onDisconnect={(id) => resolvedBridge.disconnectDevice(id)}
        onToggleReconnect={(enabled) => resolvedBridge.setReconnect(enabled)}
        onOpenBluetoothSettings={() => resolvedBridge.openBluetoothSettings()}
        onRefreshDevices={() => resolvedBridge.refreshDevices().then(() => undefined)}
      />
    </LanguageProvider>
  )
}
