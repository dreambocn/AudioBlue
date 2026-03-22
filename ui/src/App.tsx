import { useEffect, useMemo, useState } from 'react'
import { resolveBridge } from './bridge'
import type { BackendBridge, BridgeEvent } from './bridge/types'
import { TrayQuickPanel } from './components/TrayQuickPanel'
import { AutomationPage } from './pages/AutomationPage'
import { DevicesPage } from './pages/DevicesPage'
import { OverviewPage } from './pages/OverviewPage'
import { SettingsPage } from './pages/SettingsPage'
import type { AppRoute, AppState, DeviceRule, DeviceViewModel, NotificationPolicy, ThemeMode } from './types'
import './App.css'

const defaultBridge = resolveBridge()

const navItems: { key: AppRoute; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'devices', label: 'Devices' },
  { key: 'automation', label: 'Automation' },
  { key: 'settings', label: 'Settings' },
]

const updateDeviceRule = (
  devices: DeviceViewModel[],
  deviceId: string,
  patch: Partial<DeviceRule>,
) =>
  devices.map((device) =>
    device.id === deviceId
      ? {
          ...device,
          rule: { ...device.rule, ...patch },
        }
      : device,
  )

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

function App({ bridge = defaultBridge }: AppProps) {
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

  const activeDevice = useMemo(
    () => state?.devices.find((device) => device.id === state.connection.currentDeviceId),
    [state],
  )

  const handleConnect = async (deviceId: string) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      devices: state.devices.map((device) => ({
        ...device,
        isConnected: device.id === deviceId,
      })),
      connection: {
        status: 'connected',
        currentDeviceId: deviceId,
      },
    })
    await bridge.connectDevice(deviceId)
  }

  const handleDisconnect = async (deviceId: string) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      devices: state.devices.map((device) =>
        device.id === deviceId ? { ...device, isConnected: false } : device,
      ),
      connection: {
        status: 'disconnected',
      },
    })
    await bridge.disconnectDevice(deviceId)
  }

  const handleToggleFavorite = async (deviceId: string, nextFavorite: boolean) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      devices: state.devices.map((device) =>
        device.id === deviceId ? { ...device, isFavorite: nextFavorite } : device,
      ),
    })
  }

  const handleToggleAppearRule = async (deviceId: string, enabled: boolean) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      devices: updateDeviceRule(state.devices, deviceId, {
        autoConnectOnAppear: enabled,
        mode: enabled ? 'appear' : 'manual',
      }),
    })
    await bridge.updateDeviceRule(deviceId, {
      autoConnectOnAppear: enabled,
      mode: enabled ? 'appear' : 'manual',
    })
  }

  const handleThemeChange = async (theme: ThemeMode) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      ui: {
        ...state.ui,
        themeMode: theme,
      },
    })
    await bridge.setTheme(theme)
  }

  const handleAutostartChange = async (enabled: boolean) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      startup: {
        ...state.startup,
        autostart: enabled,
      },
    })
    await bridge.setAutostart(enabled)
  }

  const handleNotificationPolicyChange = async (policy: NotificationPolicy) => {
    if (!state) {
      return
    }
    setState({
      ...state,
      notifications: { policy },
    })
    await bridge.setNotificationPolicy(policy)
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
    <div className="app-root">
      <aside className="left-nav">
        <h1>AudioBlue</h1>
        <p className="muted">Win11 Hybrid Control Center</p>
        <nav aria-label="Main Navigation">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-button ${route === item.key ? 'active' : ''}`}
              onClick={() => setRoute(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content-shell">
        <header className="command-bar">
          <h2>{navItems.find((item) => item.key === route)?.label}</h2>
          <button type="button" className="secondary-button" onClick={() => bridge.refreshDevices()}>
            Refresh Devices
          </button>
        </header>

        {route === 'overview' ? <OverviewPage state={state} /> : null}
        {route === 'devices' ? (
          <DevicesPage
            devices={state.devices}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            onToggleFavorite={handleToggleFavorite}
          />
        ) : null}
        {route === 'automation' ? (
          <AutomationPage devices={state.devices} onToggleAppearRule={handleToggleAppearRule} />
        ) : null}
        {route === 'settings' ? (
          <SettingsPage
            state={state}
            onThemeChange={handleThemeChange}
            onAutostartChange={handleAutostartChange}
            onNotificationPolicyChange={handleNotificationPolicyChange}
            onExportDiagnostics={handleExportDiagnostics}
          />
        ) : null}
      </main>

      <aside className="right-panel">
        <TrayQuickPanel
          currentDevice={activeDevice}
          autoConnectEnabled={state.devices.some((device) => device.rule.autoConnectOnAppear)}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
          onToggleAutoConnect={(enabled) => {
            const firstDevice = state.devices[0]
            if (!firstDevice) {
              return
            }
            void handleToggleAppearRule(firstDevice.id, enabled)
          }}
          onOpenControlCenter={() => setRoute('devices')}
          onOpenBluetoothSettings={handleOpenBluetoothSettings}
        />
      </aside>
    </div>
  )
}

export default App
