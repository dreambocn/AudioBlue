import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import type { BackendBridge, BridgeEvent } from './bridge/types'
import { useResolvedBridge } from './bridge/useResolvedBridge'
import { TrayQuickPanel } from './components/TrayQuickPanel'
import { LanguageProvider, useI18n } from './i18n'
import { AutomationPage } from './pages/AutomationPage'
import { DevicesPage } from './pages/DevicesPage'
import { OverviewPage } from './pages/OverviewPage'
import { SettingsPage } from './pages/SettingsPage'
import type {
  A2dpSourceAvailability,
  AppRoute,
  AppState,
  DeviceRulePatch,
  DeviceViewModel,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from './types'
import './App.css'

// 统一维护左侧导航，避免页面标题和按钮文本来源分散。
const navItems: { key: AppRoute; labelKey: string }[] = [
  { key: 'overview', labelKey: 'nav.overview' },
  { key: 'devices', labelKey: 'nav.devices' },
  { key: 'automation', labelKey: 'nav.automation' },
  { key: 'settings', labelKey: 'nav.settings' },
]

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

// 后端返回的是优先列表，这里把优先设备前置，其余设备保留原有顺序。
const reorderDevicesByPriority = (
  devices: DeviceViewModel[],
  prioritizedDeviceIds: string[],
) => {
  const byId = new Map(devices.map((device) => [device.id, device]))
  const prioritized = prioritizedDeviceIds
    .map((id) => byId.get(id))
    .filter((device): device is DeviceViewModel => Boolean(device))
  const remaining = devices.filter((device) => !prioritizedDeviceIds.includes(device.id))
  return [...prioritized, ...remaining]
}

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
    default:
      return state
  }
}

interface AppProps {
  bridge?: BackendBridge
}

interface ControlCenterContentProps {
  route: AppRoute
  state: AppState
  visibleDevices: DeviceViewModel[]
  audioDevices: DeviceViewModel[]
  activeDevice?: DeviceViewModel
  sourceAvailability: A2dpSourceAvailability
  setRoute: (route: AppRoute) => void
  onConnect: (deviceId: string) => Promise<void>
  onDisconnect: (deviceId: string) => Promise<void>
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => Promise<void>
  onToggleAppearRule: (deviceId: string, enabled: boolean) => Promise<void>
  onReorderPriority: (deviceIds: string[]) => Promise<void>
  onThemeChange: (theme: ThemeMode) => Promise<void>
  onAutostartChange: (enabled: boolean) => Promise<void>
  onSetReconnect: (enabled: boolean) => Promise<void>
  onNotificationPolicyChange: (policy: NotificationPolicy) => Promise<void>
  onLanguageChange: (language: LanguagePreference) => Promise<void>
  onExportDiagnostics: () => Promise<void>
  onOpenBluetoothSettings: () => Promise<void>
  onRefreshDevices: () => Promise<void>
}

function ControlCenterContent({
  route,
  state,
  visibleDevices,
  audioDevices,
  activeDevice,
  sourceAvailability,
  setRoute,
  onConnect,
  onDisconnect,
  onToggleFavorite,
  onToggleAppearRule,
  onReorderPriority,
  onThemeChange,
  onAutostartChange,
  onSetReconnect,
  onNotificationPolicyChange,
  onLanguageChange,
  onExportDiagnostics,
  onOpenBluetoothSettings,
  onRefreshDevices,
}: ControlCenterContentProps) {
  const { t } = useI18n()

  return (
    <div className="app-root">
      <aside className="left-nav">
        <h1>AudioBlue</h1>
        <p className="muted">{t('app.subtitle')}</p>
        <nav aria-label="Main Navigation">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-button ${route === item.key ? 'active' : ''}`}
              onClick={() => setRoute(item.key)}
            >
              {t(item.labelKey)}
            </button>
          ))}
        </nav>
      </aside>

      <main
        className={`workspace-shell ${route === 'overview' ? 'has-quick-actions' : 'single-pane'}`}
        data-testid="workspace-shell"
      >
        {route === 'overview' ? (
          <section
            className="workspace-quick-actions"
            data-testid="workspace-quick-actions"
          >
            <TrayQuickPanel
              currentDevice={activeDevice}
              reconnectOnNextStart={state.startup.reconnectOnNextStart}
              sourceAvailability={sourceAvailability}
              bridgeMode={state.runtime.bridgeMode}
              totalDevices={state.devices.length}
              matchedSourceDevices={audioDevices}
              debugDevices={state.devices}
              onConnect={onConnect}
              onDisconnect={onDisconnect}
              onToggleReconnect={onSetReconnect}
              onOpenBluetoothSettings={onOpenBluetoothSettings}
              onRefreshDevices={onRefreshDevices}
            />
          </section>
        ) : null}

        <section className="workspace-content" data-testid="workspace-content">
          <header className="page-header">
            <p className="page-kicker">AudioBlue</p>
            <h2>{t(navItems.find((item) => item.key === route)?.labelKey ?? 'nav.overview')}</h2>
          </header>

          {route === 'overview' ? <OverviewPage state={state} /> : null}
          {route === 'devices' ? (
            <DevicesPage
              devices={visibleDevices}
              deviceHistory={state.deviceHistory ?? []}
              onConnect={onConnect}
              onDisconnect={onDisconnect}
              onToggleFavorite={onToggleFavorite}
            />
          ) : null}
          {route === 'automation' ? (
            <AutomationPage
              devices={audioDevices}
              onToggleAppearRule={onToggleAppearRule}
              onReorderPriority={onReorderPriority}
            />
          ) : null}
          {route === 'settings' ? (
            <SettingsPage
              state={state}
              sourceAvailability={sourceAvailability}
              bridgeMode={state.runtime.bridgeMode}
              totalDevices={state.devices.length}
              matchedSourceDevices={audioDevices}
              debugDevices={state.devices}
              onThemeChange={onThemeChange}
              onLanguageChange={onLanguageChange}
              onAutostartChange={onAutostartChange}
              onNotificationPolicyChange={onNotificationPolicyChange}
              onExportDiagnostics={onExportDiagnostics}
            />
          ) : null}
        </section>
      </main>
    </div>
  )
}

function ControlCenterShell({ bridge }: { bridge: BackendBridge }) {
  const [route, setRoute] = useState<AppRoute>('overview')
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
        errorCode: event.reason instanceof Error ? event.reason.name : 'UnhandledPromiseRejection',
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

  const activeDevice = useMemo(() => {
    if (!state) {
      return undefined
    }

    return (
      state.devices.find(
        (device) =>
          device.id === state.connection.currentDeviceId && device.isConnected,
      ) ?? state.devices.find((device) => device.isConnected)
    )
  }, [state])

  const orderedDevices = useMemo(
    () =>
      state
        ? reorderDevicesByPriority(state.devices, state.prioritizedDeviceIds)
        : [],
    [state],
  )

  const audioDevices = useMemo(
    () => orderedDevices.filter((device) => device.supportsAudio),
    [orderedDevices],
  )

  const visibleDevices = useMemo(
    () =>
      orderedDevices.filter((device) => device.isConnected || device.supportsAudio) ??
      [],
    [orderedDevices],
  )

  const sourceAvailability = useMemo<A2dpSourceAvailability>(() => {
    if (!state || state.runtime.bridgeMode === 'unavailable') {
      return 'unavailable'
    }
    if (audioDevices.length === 0) {
      return 'no-source'
    }
    return 'available'
  }, [audioDevices.length, state])

  const handleConnect = async (deviceId: string) => {
    await runBridgeTask('连接设备失败', () => bridge.connectDevice(deviceId), {
      action: 'connectDevice',
      deviceId,
    })
  }

  const handleDisconnect = async (deviceId: string) => {
    await runBridgeTask('断开设备失败', () => bridge.disconnectDevice(deviceId), {
      action: 'disconnectDevice',
      deviceId,
    })
  }

  const handleToggleFavorite = async (deviceId: string, nextFavorite: boolean) => {
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

  const handleToggleAppearRule = async (deviceId: string, enabled: boolean) => {
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

  const handleThemeChange = async (theme: ThemeMode) => {
    await runBridgeTask('切换主题失败', () => bridge.setTheme(theme), {
      action: 'setTheme',
      theme,
    })
  }

  const handleReorderPriority = async (deviceIds: string[]) => {
    await runBridgeTask(
      '更新自动连接顺序失败',
      () => bridge.reorderDevicePriority(deviceIds),
      {
        action: 'reorderDevicePriority',
        deviceIds,
      },
    )
  }

  const handleAutostartChange = async (enabled: boolean) => {
    await runBridgeTask('更新随 Windows 启动设置失败', () => bridge.setAutostart(enabled), {
      action: 'setAutostart',
      enabled,
    })
  }

  const handleSetReconnect = async (enabled: boolean) => {
    await runBridgeTask('更新启动自动重连设置失败', () => bridge.setReconnect(enabled), {
      action: 'setReconnect',
      enabled,
    })
  }

  const handleNotificationPolicyChange = async (policy: NotificationPolicy) => {
    await runBridgeTask(
      '更新通知策略失败',
      () => bridge.setNotificationPolicy(policy),
      {
        action: 'setNotificationPolicy',
        policy,
      },
    )
  }

  const handleLanguageChange = async (language: LanguagePreference) => {
    await runBridgeTask('切换语言失败', () => bridge.setLanguage(language), {
      action: 'setLanguage',
      language,
    })
  }

  const handleExportDiagnostics = async () => {
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

  const handleOpenBluetoothSettings = async () => {
    await runBridgeTask(
      '打开蓝牙设置失败',
      () => bridge.openBluetoothSettings(),
      {
        action: 'openBluetoothSettings',
      },
    )
  }

  const handleRefreshDevices = async () => {
    await runBridgeTask('刷新设备失败', () => bridge.refreshDevices(), {
      action: 'refreshDevices',
    })
  }

  if (isLoading || !state) {
    return <div className="loading-shell">Loading AudioBlue control center…</div>
  }

  return (
    <LanguageProvider preference={state.ui.language}>
      <ControlCenterContent
        route={route}
        state={state}
        visibleDevices={visibleDevices}
        audioDevices={audioDevices}
        activeDevice={activeDevice}
        sourceAvailability={sourceAvailability}
        setRoute={setRoute}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        onToggleFavorite={handleToggleFavorite}
        onToggleAppearRule={handleToggleAppearRule}
        onReorderPriority={handleReorderPriority}
        onThemeChange={handleThemeChange}
        onAutostartChange={handleAutostartChange}
        onSetReconnect={handleSetReconnect}
        onNotificationPolicyChange={handleNotificationPolicyChange}
        onLanguageChange={handleLanguageChange}
        onExportDiagnostics={handleExportDiagnostics}
        onOpenBluetoothSettings={handleOpenBluetoothSettings}
        onRefreshDevices={handleRefreshDevices}
      />
    </LanguageProvider>
  )
}

function App({ bridge }: AppProps) {
  // 先解析实际桥接实现，再交给主壳层管理页面状态与副作用。
  const resolvedBridge = useResolvedBridge(bridge)

  return <ControlCenterShell bridge={resolvedBridge} />
}

export default App
