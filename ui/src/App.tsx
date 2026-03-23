import { useEffect, useMemo, useState } from 'react'
import { resolveBridge } from './bridge'
import type { BackendBridge, BridgeEvent } from './bridge/types'
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

const defaultBridge = resolveBridge()

const navItems: { key: AppRoute; labelKey: string }[] = [
  { key: 'overview', labelKey: 'nav.overview' },
  { key: 'devices', labelKey: 'nav.devices' },
  { key: 'automation', labelKey: 'nav.automation' },
  { key: 'settings', labelKey: 'nav.settings' },
]

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

const applyBridgeEvent = (state: AppState, event: BridgeEvent): AppState => {
  switch (event.type) {
    case 'devices_changed':
      return { ...state, devices: event.devices }
    case 'connection_changed':
      return { ...state, connection: event.connection }
    case 'connection_failed':
      return { ...state, connection: { ...state.connection, lastFailure: event.message } }
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
  bridge: BackendBridge
  setRoute: (route: AppRoute) => void
  onConnect: (deviceId: string) => Promise<void>
  onDisconnect: (deviceId: string) => Promise<void>
  onToggleFavorite: (deviceId: string, nextFavorite: boolean) => Promise<void>
  onToggleAppearRule: (deviceId: string, enabled: boolean) => Promise<void>
  onReorderPriority: (deviceIds: string[]) => Promise<void>
  onThemeChange: (theme: ThemeMode) => Promise<void>
  onAutostartChange: (enabled: boolean) => Promise<void>
  onNotificationPolicyChange: (policy: NotificationPolicy) => Promise<void>
  onLanguageChange: (language: LanguagePreference) => Promise<void>
  onExportDiagnostics: () => Promise<void>
  onOpenBluetoothSettings: () => Promise<void>
}

function ControlCenterContent({
  route,
  state,
  visibleDevices,
  audioDevices,
  activeDevice,
  sourceAvailability,
  bridge,
  setRoute,
  onConnect,
  onDisconnect,
  onToggleFavorite,
  onToggleAppearRule,
  onReorderPriority,
  onThemeChange,
  onAutostartChange,
  onNotificationPolicyChange,
  onLanguageChange,
  onExportDiagnostics,
  onOpenBluetoothSettings,
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

      <main className="content-shell">
        <header className="command-bar">
          <h2>{t(navItems.find((item) => item.key === route)?.labelKey ?? 'nav.overview')}</h2>
          <button
            type="button"
            className="secondary-button"
            onClick={async () => {
              await bridge.refreshDevices()
            }}
          >
            {t('command.refreshDevices')}
          </button>
        </header>

        {route === 'overview' ? (
          <OverviewPage
            state={state}
            sourceAvailability={sourceAvailability}
            bridgeMode={state.runtime.bridgeMode}
            totalDevices={state.devices.length}
            matchedSourceDevices={audioDevices}
            debugDevices={state.devices}
          />
        ) : null}
        {route === 'devices' ? (
          <DevicesPage
            devices={visibleDevices}
            sourceAvailability={sourceAvailability}
            bridgeMode={state.runtime.bridgeMode}
            totalDevices={state.devices.length}
            matchedSourceDevices={audioDevices}
            debugDevices={state.devices}
            onConnect={onConnect}
            onDisconnect={onDisconnect}
            onToggleFavorite={onToggleFavorite}
          />
        ) : null}
        {route === 'automation' ? (
          <AutomationPage
            devices={audioDevices}
            sourceAvailability={sourceAvailability}
            bridgeMode={state.runtime.bridgeMode}
            totalDevices={state.devices.length}
            matchedSourceDevices={audioDevices}
            debugDevices={state.devices}
            onToggleAppearRule={onToggleAppearRule}
            onReorderPriority={onReorderPriority}
          />
        ) : null}
        {route === 'settings' ? (
          <SettingsPage
            state={state}
            onThemeChange={onThemeChange}
            onLanguageChange={onLanguageChange}
            onAutostartChange={onAutostartChange}
            onNotificationPolicyChange={onNotificationPolicyChange}
            onExportDiagnostics={onExportDiagnostics}
          />
        ) : null}
      </main>

      <aside className="right-panel">
        <TrayQuickPanel
          currentDevice={activeDevice}
          autoConnectEnabled={audioDevices.some((device) => device.rule.autoConnectOnAppear)}
          sourceAvailability={sourceAvailability}
          bridgeMode={state.runtime.bridgeMode}
          totalDevices={state.devices.length}
          matchedSourceDevices={audioDevices}
          debugDevices={state.devices}
          onConnect={onConnect}
          onDisconnect={onDisconnect}
          onToggleAutoConnect={(enabled) => {
            const firstDevice = audioDevices[0]
            if (!firstDevice) {
              return
            }
            void onToggleAppearRule(firstDevice.id, enabled)
          }}
          onOpenControlCenter={() => setRoute('devices')}
          onOpenBluetoothSettings={onOpenBluetoothSettings}
        />
      </aside>
    </div>
  )
}

function ControlCenterShell({ bridge }: { bridge: BackendBridge }) {
  const [route, setRoute] = useState<AppRoute>('overview')
  const [state, setState] = useState<AppState | null>(null)
  const [isLoading, setIsLoading] = useState(true)

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
    if (!state) {
      return
    }
    document.documentElement.setAttribute('data-theme', state.ui.themeMode)
  }, [state])

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
    await bridge.connectDevice(deviceId)
  }

  const handleDisconnect = async (deviceId: string) => {
    await bridge.disconnectDevice(deviceId)
  }

  const handleToggleFavorite = async (deviceId: string, nextFavorite: boolean) => {
    await bridge.updateDeviceRule(deviceId, { isFavorite: nextFavorite })
  }

  const handleToggleAppearRule = async (deviceId: string, enabled: boolean) => {
    await bridge.updateDeviceRule(deviceId, {
      autoConnectOnAppear: enabled,
      mode: enabled ? 'appear' : 'manual',
    })
  }

  const handleThemeChange = async (theme: ThemeMode) => {
    await bridge.setTheme(theme)
  }

  const handleReorderPriority = async (deviceIds: string[]) => {
    await bridge.reorderDevicePriority(deviceIds)
  }

  const handleAutostartChange = async (enabled: boolean) => {
    await bridge.setAutostart(enabled)
  }

  const handleNotificationPolicyChange = async (policy: NotificationPolicy) => {
    await bridge.setNotificationPolicy(policy)
  }

  const handleLanguageChange = async (language: LanguagePreference) => {
    await bridge.setLanguage(language)
  }

  const handleExportDiagnostics = async () => {
    const exportPath = await bridge.exportDiagnostics()
    setState((current) =>
      current
        ? {
            ...current,
            diagnostics: {
              ...current.diagnostics,
              lastExportPath: exportPath,
            },
          }
        : current,
    )
  }

  const handleOpenBluetoothSettings = async () => {
    await bridge.openBluetoothSettings()
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
        bridge={bridge}
        setRoute={setRoute}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        onToggleFavorite={handleToggleFavorite}
        onToggleAppearRule={handleToggleAppearRule}
        onReorderPriority={handleReorderPriority}
        onThemeChange={handleThemeChange}
        onAutostartChange={handleAutostartChange}
        onNotificationPolicyChange={handleNotificationPolicyChange}
        onLanguageChange={handleLanguageChange}
        onExportDiagnostics={handleExportDiagnostics}
        onOpenBluetoothSettings={handleOpenBluetoothSettings}
      />
    </LanguageProvider>
  )
}

function App({ bridge = defaultBridge }: AppProps) {
  return <ControlCenterShell bridge={bridge} />
}

export default App
