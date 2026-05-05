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

const describeError = (error: unknown) =>
  error instanceof Error ? `${error.name}: ${error.message}` : String(error)

const createQuickPanelFailureState = (message: string): AppState => ({
  devices: [],
  deviceHistory: [],
  prioritizedDeviceIds: [],
  recentActivity: [],
  connection: {
    status: 'disconnected',
    currentPhase: 'failed',
    lastFailure: message,
    lastErrorMessage: message,
  },
  startup: {
    autostart: false,
    backgroundStart: false,
    delaySeconds: 0,
    reconnectOnNextStart: false,
  },
  ui: {
    themeMode: 'system',
    language: 'system',
    showAudioOnly: true,
    diagnosticsMode: true,
  },
  notifications: {
    policy: 'failures',
  },
  diagnostics: {
    lastProbe: 'Bridge unavailable',
    probeResult: message,
    logRetentionDays: 90,
    activityEventCount: 0,
    connectionAttemptCount: 0,
    logRecordCount: 0,
    recentErrors: [
      {
        title: '托盘快照读取失败',
        detail: message,
        errorCode: 'TrayInitialStateError',
      },
    ],
  },
  runtime: {
    bridgeMode: 'unavailable',
    chrome: 'custom',
    isMaximized: false,
    canMinimize: false,
    canMaximize: false,
    canClose: false,
  },
})

export function TrayQuickPanelView({ bridge }: TrayQuickPanelViewProps) {
  const resolvedBridge = useResolvedBridge(bridge)
  const [state, setState] = useState<AppState | null>(null)

  useEffect(() => {
    // 订阅桥接事件，并把增量更新折叠进本地状态，保持托盘快速面板与主界面一致。
    let alive = true
    const loadInitialState = async () => {
      try {
        const initial = await resolvedBridge.getInitialState()
        if (alive) {
          setState(initial)
        }
      } catch (error) {
        const detail = describeError(error)
        try {
          await resolvedBridge.recordClientEvent({
            area: 'tray',
            eventType: 'tray.initial_state.failed',
            level: 'error',
            title: '托盘快照读取失败',
            detail,
            errorCode: error instanceof Error ? error.name : 'UnknownError',
            details: {
              action: 'getInitialState',
            },
          })
        } catch {
          // 记录失败不能再次制造未处理 Promise。
        }
        if (alive) {
          setState(createQuickPanelFailureState(detail))
        }
      }
    }

    void loadInitialState()

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
  const runTrayAction = async (
    action: string,
    task: () => Promise<unknown>,
    details?: Record<string, unknown>,
  ) => {
    try {
      await task()
    } catch (error) {
      try {
        await resolvedBridge.recordClientEvent({
          area: 'tray',
          eventType: 'tray.action.failed',
          level: 'error',
          title: '托盘操作失败',
          detail: describeError(error),
          errorCode: error instanceof Error ? error.name : 'UnknownError',
          details: {
            action,
            ...details,
          },
        })
      } catch {
        // 托盘操作失败已被兜底，记录链路自身失败时静默降级。
      }
    }
  }

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
        onConnect={(id) =>
          void runTrayAction('connectDevice', () => resolvedBridge.connectDevice(id), {
            deviceId: id,
          })
        }
        onDisconnect={(id) =>
          void runTrayAction('disconnectDevice', () => resolvedBridge.disconnectDevice(id), {
            deviceId: id,
          })
        }
        onToggleReconnect={(enabled) =>
          void runTrayAction('setReconnect', () => resolvedBridge.setReconnect(enabled), {
            enabled,
          })
        }
        onOpenBluetoothSettings={() =>
          void runTrayAction('openBluetoothSettings', () =>
            resolvedBridge.openBluetoothSettings(),
          )
        }
        onRefreshDevices={() =>
          void runTrayAction('refreshDevices', () => resolvedBridge.refreshDevices())
        }
      />
    </LanguageProvider>
  )
}
