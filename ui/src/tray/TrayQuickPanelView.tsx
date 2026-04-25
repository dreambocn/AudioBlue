import { useEffect, useState } from 'react'
import type { BackendBridge } from '../bridge/types'
import { useResolvedBridge } from '../bridge/useResolvedBridge'
import { TrayQuickPanel } from '../components/TrayQuickPanel'
import { LanguageProvider } from '../i18n'
import type { AppState } from '../types'
import {
  selectActiveDevice,
  selectA2dpAvailability,
  selectAudioDevices,
} from '../state/selectors'

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
      if (event.type === 'runtime_changed') {
        setState((current) => (current ? { ...current, runtime: event.runtime } : current))
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

  // 托盘视图直接复用主界面的派生选择器，确保连接判定与健康状态口径一致。
  const activeDevice = selectActiveDevice(state.devices, state.connection)
  const audioDevices = selectAudioDevices(state)
  const sourceAvailability = selectA2dpAvailability(state)

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
