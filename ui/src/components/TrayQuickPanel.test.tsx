// 覆盖托盘快速面板在连接态、无活动设备态下的关键交互。
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TrayQuickPanel } from './TrayQuickPanel'
import { LanguageProvider } from '../i18n'
import { TrayQuickPanelView } from '../tray/TrayQuickPanelView'
import type { BackendBridge } from '../bridge/types'
import type { AppState, DeviceViewModel } from '../types'

const connectedDevice: DeviceViewModel = {
  // 复用一份已连接设备，避免每个用例重复拼装相同的状态快照。
  id: 'device-buds',
  name: 'Galaxy Buds',
  isConnected: true,
  isConnecting: false,
  isFavorite: true,
  isIgnored: false,
  supportsAudio: true,
  presentInLastScan: true,
  lastSeen: 'now',
  lastResult: 'Connected',
  rule: {
    mode: 'appear',
    autoConnectOnStartup: false,
    autoConnectOnAppear: true,
  },
}

const quickPanelState: AppState = {
  devices: [connectedDevice],
  deviceHistory: [],
  prioritizedDeviceIds: ['device-buds'],
  recentActivity: [],
  connection: {
    status: 'disconnected',
  },
  startup: {
    autostart: false,
    backgroundStart: false,
    delaySeconds: 0,
    reconnectOnNextStart: false,
  },
  ui: {
    themeMode: 'system',
    language: 'en-US',
    showAudioOnly: true,
    diagnosticsMode: false,
  },
  notifications: {
    policy: 'failures',
  },
  diagnostics: {
    logRetentionDays: 90,
    activityEventCount: 0,
    connectionAttemptCount: 0,
    logRecordCount: 0,
    recentErrors: [],
  },
  runtime: {
    bridgeMode: 'native',
    chrome: 'custom',
    isMaximized: false,
    canMinimize: true,
    canMaximize: true,
    canClose: true,
  },
}

const createTrayBridge = (
  overrides?: Partial<BackendBridge>,
  state: AppState = quickPanelState,
): BackendBridge => ({
  async getInitialState() {
    return structuredClone(state)
  },
  async refreshDevices() {
    return structuredClone(state.devices)
  },
  connectDevice: vi.fn(async () => undefined),
  disconnectDevice: vi.fn(async () => undefined),
  updateDeviceRule: vi.fn(async () => undefined),
  reorderDevicePriority: vi.fn(async () => undefined),
  deleteDeviceHistory: vi.fn(async () => undefined),
  clearDeviceHistory: vi.fn(async () => undefined),
  setAutostart: vi.fn(async () => undefined),
  setReconnect: vi.fn(async () => undefined),
  setTheme: vi.fn(async () => undefined),
  syncWindowTheme: vi.fn(async () => undefined),
  setLanguage: vi.fn(async () => undefined),
  setNotificationPolicy: vi.fn(async () => undefined),
  minimizeWindow: vi.fn(async () => undefined),
  toggleMaximizeWindow: vi.fn(async () => undefined),
  closeMainWindow: vi.fn(async () => undefined),
  openBluetoothSettings: vi.fn(async () => undefined),
  exportSupportBundle: vi.fn(async () => ''),
  exportDiagnostics: vi.fn(async () => ''),
  recordClientEvent: vi.fn(async () => undefined),
  onEvent: vi.fn(() => () => undefined),
  ...overrides,
})

describe('TrayQuickPanel', () => {
  it('shows connection status and can disconnect current device', async () => {
    const onDisconnect = vi.fn()

    render(
      <LanguageProvider preference="en-US">
        <TrayQuickPanel
          currentDevice={connectedDevice}
          reconnectOnNextStart
          sourceAvailability="available"
          bridgeMode="native"
          totalDevices={1}
          matchedSourceDevices={[connectedDevice]}
          debugDevices={[connectedDevice]}
          onDisconnect={onDisconnect}
          onConnect={vi.fn()}
          onToggleReconnect={vi.fn()}
          onOpenBluetoothSettings={vi.fn()}
          onRefreshDevices={vi.fn()}
        />
      </LanguageProvider>,
    )

    expect(screen.getByText('Connected to Galaxy Buds')).toBeVisible()
    expect(screen.queryByText(/Raw device ID/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(onDisconnect).toHaveBeenCalledWith('device-buds')
  })

  it('uses the cockpit wording for quick control copy', () => {
    render(
      <LanguageProvider preference="en-US">
        <TrayQuickPanel
          currentDevice={connectedDevice}
          reconnectOnNextStart
          sourceAvailability="available"
          bridgeMode="native"
          totalDevices={1}
          matchedSourceDevices={[connectedDevice]}
          debugDevices={[connectedDevice]}
          onDisconnect={vi.fn()}
          onConnect={vi.fn()}
          onToggleReconnect={vi.fn()}
          onOpenBluetoothSettings={vi.fn()}
          onRefreshDevices={vi.fn()}
        />
      </LanguageProvider>,
    )

    expect(screen.getByText('Cockpit quick controls')).toBeVisible()
  })

  it('renders reconnect control as a stateful button below the action row', async () => {
    const onToggleReconnect = vi.fn()

    render(
      <LanguageProvider preference="en-US">
        <TrayQuickPanel
          currentDevice={connectedDevice}
          reconnectOnNextStart
          sourceAvailability="available"
          bridgeMode="native"
          totalDevices={1}
          matchedSourceDevices={[connectedDevice]}
          debugDevices={[connectedDevice]}
          onDisconnect={vi.fn()}
          onConnect={vi.fn()}
          onToggleReconnect={onToggleReconnect}
          onOpenBluetoothSettings={vi.fn()}
          onRefreshDevices={vi.fn()}
        />
      </LanguageProvider>,
    )

    const actionRow = screen.getByTestId('tray-action-row')
    expect(within(actionRow).getByRole('button', { name: 'Disconnect' })).toBeVisible()
    expect(within(actionRow).getByRole('button', { name: 'Refresh Devices' })).toBeVisible()
    expect(
      within(actionRow).getByRole('button', { name: 'Open Bluetooth Settings' }),
    ).toBeVisible()
    expect(
      within(actionRow).queryByRole('checkbox', {
        name: 'Reconnect on next start',
      }),
    ).not.toBeInTheDocument()

    const reconnectButton = screen.getByRole('button', {
      name: 'Reconnect on next start · On',
    })
    expect(reconnectButton).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(reconnectButton)
    expect(onToggleReconnect).toHaveBeenCalledWith(false)
  })

  it('shows unavailable quick panel state when tray initial loading fails', async () => {
    const recordClientEvent = vi.fn(async () => undefined)
    const bridge = createTrayBridge({
      getInitialState: vi.fn(async () => {
        throw new Error('托盘快照读取失败')
      }),
      recordClientEvent,
    })

    render(<TrayQuickPanelView bridge={bridge} />)

    expect(await screen.findByText('Bridge unavailable')).toBeVisible()
    expect(recordClientEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        eventType: 'tray.initial_state.failed',
        title: '托盘快照读取失败',
      }),
    )
  })

  it('records quick panel action failures without unhandled rejection', async () => {
    const availableDevice = {
      ...connectedDevice,
      isConnected: false,
      presentInLastScan: true,
    }
    const recordClientEvent = vi.fn(async () => undefined)
    const bridge = createTrayBridge({
      connectDevice: vi.fn(async () => {
        throw new Error('连接失败')
      }),
      disconnectDevice: vi.fn(async () => {
        throw new Error('断开失败')
      }),
      setReconnect: vi.fn(async () => {
        throw new Error('设置失败')
      }),
      refreshDevices: vi.fn(async () => {
        throw new Error('刷新失败')
      }),
      openBluetoothSettings: vi.fn(async () => {
        throw new Error('打开设置失败')
      }),
      recordClientEvent,
    }, {
      ...quickPanelState,
      devices: [availableDevice],
      prioritizedDeviceIds: [availableDevice.id],
    })

    render(<TrayQuickPanelView bridge={bridge} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Connect' }))
    await userEvent.click(screen.getByRole('button', { name: 'Refresh Devices' }))
    await userEvent.click(screen.getByRole('button', { name: 'Open Bluetooth Settings' }))
    await userEvent.click(screen.getByRole('button', { name: 'Reconnect on next start · Off' }))

    expect(recordClientEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        eventType: 'tray.action.failed',
        title: '托盘操作失败',
      }),
    )
    expect(recordClientEvent).toHaveBeenCalledTimes(4)
  })
})
