import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import type { BackendBridge, BridgeEvent } from '../bridge/types'
import type {
  A2dpSourceAvailability,
  AppState,
  AppRoute,
  DeviceRulePatch,
  DeviceViewModel,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'
import {
  selectActiveDevice,
  selectA2dpAvailability,
  selectAudioDevices,
  selectCockpitCandidate,
  selectVisibleDevices,
} from './selectors'

// 当用户选择“跟随系统”时，界面主题始终由系统深浅色偏好驱动。
const getSystemTheme = (): Exclude<ThemeMode, 'system'> =>
  globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

const subscribeSystemTheme = (onStoreChange: () => void) => {
  const mediaQuery = globalThis.matchMedia?.('(prefers-color-scheme: dark)')
  if (!mediaQuery) {
    return () => undefined
  }

  mediaQuery.addEventListener('change', onStoreChange)
  return () => {
    mediaQuery.removeEventListener('change', onStoreChange)
  }
}

// 将显式主题与系统主题收敛为最终渲染主题，组件只消费确定值。
const useResolvedTheme = (themeMode?: ThemeMode): Exclude<ThemeMode, 'system'> => {
  const systemTheme = useSyncExternalStore<Exclude<ThemeMode, 'system'>>(
    subscribeSystemTheme,
    getSystemTheme,
    () => 'light',
  )

  if (themeMode === 'light' || themeMode === 'dark') {
    return themeMode
  }

  return systemTheme
}

// 仅替换目标设备的规则，保持其余设备引用稳定，减少无关重渲染。
const updateDeviceRule = (
  devices: DeviceViewModel[],
  deviceId: string,
  patch: DeviceRulePatch,
) =>
  devices.map((device) =>
    device.id === deviceId
      ? {
          ...device,
          rule: { ...device.rule, ...patch },
        }
      : device,
  )

// 将桥接层事件统一折叠成前端状态快照，便于 React 端只维护单一状态源。
const applyBridgeEvent = (state: AppState, event: BridgeEvent): AppState => {
  switch (event.type) {
    case 'devices_changed':
      return { ...state, devices: event.devices }
    case 'history_changed':
      return { ...state, deviceHistory: event.deviceHistory }
    case 'activity_changed':
      return { ...state, recentActivity: event.recentActivity }
    case 'connection_changed':
      return { ...state, connection: event.connection }
    case 'connection_failed':
      return {
        ...state,
        connection: {
          ...state.connection,
          lastFailure: event.message,
          lastErrorMessage: event.message,
        },
      }
    case 'rules_changed':
      return {
        ...state,
        devices: updateDeviceRule(state.devices, event.deviceId, event.rule),
      }
    case 'priorities_changed':
      return {
        ...state,
        prioritizedDeviceIds: event.prioritizedDeviceIds,
      }
    case 'settings_changed':
      return {
        ...state,
        startup: event.settings.startup,
        ui: event.settings.ui,
        notifications: event.settings.notifications,
      }
    case 'diagnostics_changed':
      return { ...state, diagnostics: event.diagnostics }
    case 'runtime_changed':
      return { ...state, runtime: event.runtime }
    default:
      return state
  }
}

interface ControlCenterViewModel {
  route: AppRoute
  setRoute: (route: AppRoute) => void
  state: AppState | null
  isLoading: boolean
  resolvedTheme: Exclude<ThemeMode, 'system'>
  visibleDevices: DeviceViewModel[]
  audioDevices: DeviceViewModel[]
  activeDevice?: DeviceViewModel
  cockpitCandidate?: DeviceViewModel
  sourceAvailability: A2dpSourceAvailability
  connectDevice: (deviceId: string) => Promise<void>
  disconnectDevice: (deviceId: string) => Promise<void>
  toggleFavorite: (deviceId: string, nextFavorite: boolean) => Promise<void>
  toggleAppearRule: (deviceId: string, enabled: boolean) => Promise<void>
  reorderPriority: (deviceIds: string[]) => Promise<void>
  setTheme: (theme: ThemeMode) => Promise<void>
  setAutostart: (enabled: boolean) => Promise<void>
  setReconnect: (enabled: boolean) => Promise<void>
  setNotificationPolicy: (policy: NotificationPolicy) => Promise<void>
  setLanguage: (language: LanguagePreference) => Promise<void>
  minimizeWindow: () => Promise<void>
  toggleMaximizeWindow: () => Promise<void>
  closeMainWindow: () => Promise<void>
  exportDiagnostics: () => Promise<void>
  openBluetoothSettings: () => Promise<void>
  refreshDevices: () => Promise<void>
}

export function useControlCenterModel(
  bridge: BackendBridge,
): ControlCenterViewModel {
  const [route, setRoute] = useState<AppRoute>('cockpit')
  const [state, setState] = useState<AppState | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const resolvedTheme = useResolvedTheme(state?.ui.themeMode)

  const recordBridgeFailure = async (
    title: string,
    error: unknown,
    details?: Record<string, unknown>,
  ) => {
    const detail =
      error instanceof Error ? `${error.name}: ${error.message}` : String(error)
    try {
      await bridge.recordClientEvent({
        area: 'ui',
        eventType: 'ui.action.failed',
        level: 'error',
        title,
        detail,
        errorCode: error instanceof Error ? error.name : 'UnknownError',
        details,
      })
    } catch {
      return
    }
  }

  const runBridgeTask = async <T,>(
    title: string,
    action: () => Promise<T>,
    details?: Record<string, unknown>,
  ): Promise<T | undefined> => {
    try {
      return await action()
    } catch (error) {
      await recordBridgeFailure(title, error, details)
      return undefined
    }
  }

  useEffect(() => {
    let alive = true
    bridge.getInitialState().then((initialState) => {
      if (!alive) {
        return
      }
      setState(initialState)
      setIsLoading(false)
    })

    const unsubscribe = bridge.onEvent((event) => {
      setState((current) => (current ? applyBridgeEvent(current, event) : current))
    })

    return () => {
      alive = false
      unsubscribe()
    }
  }, [bridge])

  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      void bridge.recordClientEvent({
        area: 'ui',
        eventType: 'ui.window.error',
        level: 'error',
        title: '界面运行错误',
        detail: event.message,
        errorCode: 'WindowError',
        details: {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        },
      })
    }
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason =
        event.reason instanceof Error
          ? `${event.reason.name}: ${event.reason.message}`
          : String(event.reason)
      void bridge.recordClientEvent({
        area: 'ui',
        eventType: 'ui.promise_rejection',
        level: 'error',
        title: '未处理的 Promise 异常',
        detail: reason,
        errorCode:
          event.reason instanceof Error ? event.reason.name : 'UnhandledPromiseRejection',
      })
    }

    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleUnhandledRejection)

    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
    }
  }, [bridge])

  useEffect(() => {
    if (!state) {
      return
    }
    document.documentElement.setAttribute('data-theme', resolvedTheme)
    void bridge.syncWindowTheme(resolvedTheme)
  }, [bridge, resolvedTheme, state])

  const activeDevice = useMemo(
    () => (state ? selectActiveDevice(state.devices, state.connection) : undefined),
    [state],
  )
  const cockpitCandidate = useMemo(
    () => (state ? selectCockpitCandidate(state) : undefined),
    [state],
  )
  const visibleDevices = useMemo(
    () => (state ? selectVisibleDevices(state) : []),
    [state],
  )
  const audioDevices = useMemo(() => (state ? selectAudioDevices(state) : []), [state])
  const sourceAvailability = useMemo<A2dpSourceAvailability>(
    () => (state ? selectA2dpAvailability(state) : 'unavailable'),
    [state],
  )

  const connectDevice = async (deviceId: string) => {
    await runBridgeTask('连接设备失败', () => bridge.connectDevice(deviceId), {
      action: 'connectDevice',
      deviceId,
    })
  }

  const disconnectDevice = async (deviceId: string) => {
    await runBridgeTask('断开设备失败', () => bridge.disconnectDevice(deviceId), {
      action: 'disconnectDevice',
      deviceId,
    })
  }

  const toggleFavorite = async (deviceId: string, nextFavorite: boolean) => {
    await runBridgeTask(
      '更新收藏状态失败',
      () => bridge.updateDeviceRule(deviceId, { isFavorite: nextFavorite }),
      {
        action: 'updateDeviceRule',
        deviceId,
        nextFavorite,
      },
    )
  }

  const toggleAppearRule = async (deviceId: string, enabled: boolean) => {
    await runBridgeTask(
      '更新再次出现自动连接规则失败',
      () =>
        bridge.updateDeviceRule(deviceId, {
          autoConnectOnAppear: enabled,
          mode: enabled ? 'appear' : 'manual',
        }),
      {
        action: 'updateDeviceRule',
        deviceId,
        enabled,
      },
    )
  }

  const reorderPriority = async (deviceIds: string[]) => {
    await runBridgeTask(
      '更新自动连接顺序失败',
      () => bridge.reorderDevicePriority(deviceIds),
      {
        action: 'reorderDevicePriority',
        deviceIds,
      },
    )
  }

  const setTheme = async (theme: ThemeMode) => {
    await runBridgeTask('切换主题失败', () => bridge.setTheme(theme), {
      action: 'setTheme',
      theme,
    })
  }

  const setAutostart = async (enabled: boolean) => {
    await runBridgeTask('更新随 Windows 启动设置失败', () => bridge.setAutostart(enabled), {
      action: 'setAutostart',
      enabled,
    })
  }

  const setReconnect = async (enabled: boolean) => {
    await runBridgeTask('更新启动自动重连设置失败', () => bridge.setReconnect(enabled), {
      action: 'setReconnect',
      enabled,
    })
  }

  const setNotificationPolicy = async (policy: NotificationPolicy) => {
    await runBridgeTask('更新通知策略失败', () => bridge.setNotificationPolicy(policy), {
      action: 'setNotificationPolicy',
      policy,
    })
  }

  const setLanguage = async (language: LanguagePreference) => {
    await runBridgeTask('切换语言失败', () => bridge.setLanguage(language), {
      action: 'setLanguage',
      language,
    })
  }

  const minimizeWindow = async () => {
    await runBridgeTask('最小化窗口失败', () => bridge.minimizeWindow(), {
      action: 'minimizeWindow',
    })
  }

  const toggleMaximizeWindow = async () => {
    await runBridgeTask('切换窗口最大化状态失败', () => bridge.toggleMaximizeWindow(), {
      action: 'toggleMaximizeWindow',
    })
  }

  const closeMainWindow = async () => {
    await runBridgeTask('隐藏主窗口失败', () => bridge.closeMainWindow(), {
      action: 'closeMainWindow',
    })
  }

  const exportDiagnostics = async () => {
    const exportPath = await runBridgeTask(
      '导出支持包失败',
      () => bridge.exportSupportBundle(),
      {
        action: 'exportSupportBundle',
      },
    )
    if (!exportPath) {
      return
    }
    setState((current) =>
      current
        ? {
            ...current,
            diagnostics: {
              ...current.diagnostics,
              lastSupportBundlePath: exportPath,
              lastSupportBundleAt: new Date().toISOString(),
              lastExportPath: exportPath,
              lastExportAt: new Date().toISOString(),
            },
          }
        : current,
    )
  }

  const openBluetoothSettings = async () => {
    await runBridgeTask('打开蓝牙设置失败', () => bridge.openBluetoothSettings(), {
      action: 'openBluetoothSettings',
    })
  }

  const refreshDevices = async () => {
    await runBridgeTask('刷新设备失败', () => bridge.refreshDevices(), {
      action: 'refreshDevices',
    })
  }

  return {
    route,
    setRoute,
    state,
    isLoading,
    resolvedTheme,
    visibleDevices,
    audioDevices,
    activeDevice,
    cockpitCandidate,
    sourceAvailability,
    connectDevice,
    disconnectDevice,
    toggleFavorite,
    toggleAppearRule,
    reorderPriority,
    setTheme,
    setAutostart,
    setReconnect,
    setNotificationPolicy,
    setLanguage,
    minimizeWindow,
    toggleMaximizeWindow,
    closeMainWindow,
    exportDiagnostics,
    openBluetoothSettings,
    refreshDevices,
  }
}
