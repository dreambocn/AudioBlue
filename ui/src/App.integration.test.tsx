// 覆盖控制中心在 mock bridge 下的主要页面联动与用户交互。
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { createMockBridge } from './bridge/mockBridge'
import type { BackendBridge, BridgeEvent } from './bridge/types'
import type { AppState, DeviceViewModel } from './types'

afterEach(() => {
  window.location.hash = ''
})

describe('AudioBlue Control Center integration', () => {
  // 基线快照同时覆盖设备列表、历史、诊断与设置，便于各用例按需覆写局部字段。
  const baseState = {
    devices: [
      {
        id: 'device-1',
        name: 'Surface Headphones',
        isConnected: false,
        isConnecting: false,
        isFavorite: false,
        isIgnored: false,
        supportsAudio: true,
        presentInLastScan: true,
        lastSeen: 'just now',
        lastResult: 'Ready to connect',
        rule: {
          mode: 'manual',
          autoConnectOnStartup: false,
          autoConnectOnAppear: false,
        },
      },
      {
        id: 'device-2',
        name: 'Studio Speaker',
        isConnected: false,
        isConnecting: false,
        isFavorite: false,
        isIgnored: false,
        supportsAudio: true,
        presentInLastScan: true,
        lastSeen: '1m ago',
        lastResult: 'Ready to connect',
        rule: {
          mode: 'manual',
          autoConnectOnStartup: false,
          autoConnectOnAppear: false,
        },
      },
    ],
    prioritizedDeviceIds: ['device-1', 'device-2'],
    recentActivity: [
      {
        id: 'evt-1',
        area: 'connection',
        eventType: 'connection.failed',
        level: 'error',
        title: '连接失败',
        detail: 'Surface Headphones 连接超时。',
        happenedAt: '2026-03-25T10:00:00+00:00',
        deviceId: 'device-1',
      },
    ],
    connection: {
      status: 'disconnected',
      currentPhase: 'disconnected',
      lastAttemptAt: '2026-03-25T10:00:00+00:00',
      lastErrorCode: 'connection.timeout',
      lastErrorMessage: 'Surface Headphones 连接超时。',
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
      lastProbe: '2026-03-25T10:00:00+00:00',
      probeResult: '检测到最近一次连接失败。',
      databasePath: 'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\audioblue.db',
      logRetentionDays: 90,
      activityEventCount: 3,
      connectionAttemptCount: 2,
      logRecordCount: 12,
      recentErrors: [
        {
          title: '连接失败',
          detail: 'Surface Headphones 连接超时。',
          happenedAt: '2026-03-25T10:00:00+00:00',
        },
      ],
    },
    runtime: {
      bridgeMode: 'native',
      chrome: 'custom',
      isMaximized: false,
      canMinimize: true,
      canMaximize: true,
      canClose: true,
    },
    deviceHistory: [
      {
        id: 'device-archived',
        name: 'Archived Receiver',
        supportsAudio: true,
        firstSeen: '2026-03-20T10:00:00+00:00',
        lastSeen: '2026-03-20T11:00:00+00:00',
        lastConnectionAt: '2026-03-20T10:55:00+00:00',
        lastResult: 'Connection timed out before audio could start.',
        lastFailureAt: '2026-03-20T10:55:00+00:00',
        successCount: 1,
        failureCount: 2,
        savedRule: {
          isFavorite: true,
          isIgnored: false,
          autoConnectOnAppear: true,
          priority: 2,
        },
      },
    ],
  } as AppState & {
    deviceHistory: Array<{
      id: string
      name: string
      supportsAudio: boolean
      lastSeen: string
      lastConnectionAt?: string
      lastResult: string
      savedRule: {
        isFavorite: boolean
        isIgnored: boolean
        autoConnectOnAppear: boolean
        priority: number | null
      }
    }>
  }

  const createStaticBridge = (state: AppState): BackendBridge => ({
    async getInitialState() {
      return structuredClone(state)
    },
    async refreshDevices() {
      return structuredClone(state.devices)
    },
    async connectDevice() {},
    async disconnectDevice() {},
    async updateDeviceRule() {},
    async reorderDevicePriority() {},
    async setAutostart() {},
    async setReconnect() {},
    async setTheme() {},
    async syncWindowTheme() {},
    async setLanguage() {},
    async setNotificationPolicy() {},
    async minimizeWindow() {},
    async toggleMaximizeWindow() {},
    async closeMainWindow() {},
    async openBluetoothSettings() {},
    async exportSupportBundle() {
      return ''
    },
    async exportDiagnostics() {
      return ''
    },
    async recordClientEvent() {},
    onEvent() {
      return () => undefined
    },
  })

  const reorderDevices = (devices: DeviceViewModel[], orderedIds: string[]) => {
    const byId = new Map(devices.map((device) => [device.id, device]))
    return orderedIds
      .map((id) => byId.get(id))
      .filter((device): device is DeviceViewModel => Boolean(device))
  }

  const createMutableBridge = (initial: AppState) => {
    const listeners = new Set<(event: BridgeEvent) => void>()
    let state = structuredClone(initial)

    const emit = (event: BridgeEvent) => {
      listeners.forEach((listener) => listener(event))
    }

    const bridge = {
      async getInitialState() {
        return structuredClone(state)
      },
      async refreshDevices() {
        emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
        return structuredClone(state.devices)
      },
      connectDevice: vi.fn(async () => undefined),
      disconnectDevice: vi.fn(async () => undefined),
      updateDeviceRule: vi.fn(async (deviceId, patch) => {
        state = {
          ...state,
          devices: state.devices.map((device) =>
            device.id === deviceId
              ? {
                  ...device,
                  isFavorite:
                    typeof patch.isFavorite === 'boolean'
                      ? patch.isFavorite
                      : device.isFavorite,
                }
              : device,
          ),
        }
        emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      }),
      reorderDevicePriority: vi.fn(async (deviceIds) => {
        state = {
          ...state,
          prioritizedDeviceIds: [...deviceIds],
          devices: reorderDevices(state.devices, deviceIds),
        }
        emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      }),
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
      onEvent(handler) {
        listeners.add(handler)
        return () => {
          listeners.delete(handler)
        }
      },
      emitRuntime(runtime: AppState['runtime']) {
        state = {
          ...state,
          runtime,
        }
        emit({
          type: 'runtime_changed',
          runtime: structuredClone(state.runtime),
        })
      },
    } as BackendBridge & {
      minimizeWindow: ReturnType<typeof vi.fn>
      toggleMaximizeWindow: ReturnType<typeof vi.fn>
      closeMainWindow: ReturnType<typeof vi.fn>
      emitRuntime: (runtime: AppState['runtime']) => void
    }
    return bridge
  }

  const createChromeState = (overrides?: Partial<AppState>) =>
    ({
      ...structuredClone(baseState),
      ...overrides,
      runtime: {
        ...structuredClone(baseState.runtime),
        chrome: 'custom',
        isMaximized: false,
        canMinimize: true,
        canMaximize: true,
        canClose: true,
        ...(overrides?.runtime ?? {}),
      },
    }) as AppState

  const createLongTextState = () => {
    const longDeviceName =
      'Surface Headphones Ultra Long Name For Regression Coverage Across Chrome And Device Cards'
    const longMessage =
      '连接失败原因说明非常长，需要覆盖标题栏摘要、托盘副标题以及历史结果文案在窄宽度下的收缩行为。'
    const longSupportBundlePath =
      'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\support-bundles\\nested\\nested\\nested\\nested\\support-bundle-2026-03-25-very-long-name.zip'

    return createChromeState({
      devices: [
        {
          ...structuredClone(baseState.devices[0]),
          name: longDeviceName,
          lastResult: longMessage,
        },
        structuredClone(baseState.devices[1]),
      ],
      prioritizedDeviceIds: ['device-1', 'device-2'],
      connection: {
        ...structuredClone(baseState.connection),
        currentDeviceName: longDeviceName,
        lastErrorMessage: longMessage,
      },
      diagnostics: {
        ...structuredClone(baseState.diagnostics),
        lastSupportBundlePath: longSupportBundlePath,
        lastSupportBundleAt: '2026-03-25T10:30:00+00:00',
      },
      deviceHistory: [
        {
          ...structuredClone(baseState.deviceHistory[0]),
          name: longDeviceName,
          lastResult: longMessage,
        },
      ],
    })
  }

  it('renders five workspace navigation items and opens cockpit by default', async () => {
    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByRole('button', { name: 'Cockpit' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Devices' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Automation' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Diagnostics' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Preferences' })).toBeVisible()
    expect(
      await within(screen.getByTestId('workspace-content')).findByRole('heading', {
        name: 'Connection cockpit',
      }),
    ).toBeVisible()
    expect(await screen.findByText('设备已连接')).toBeVisible()
  })

  it('renders custom window chrome with workspace name and connection summary', async () => {
    render(<App bridge={createStaticBridge(createChromeState())} />)

    const chrome = await screen.findByTestId('window-chrome')
    expect(within(chrome).getByText('AudioBlue')).toBeVisible()
    expect(within(chrome).getByText('Cockpit')).toBeVisible()
    expect(within(chrome).getByText('Surface Headphones')).toBeVisible()
  })

  it('keeps a continuous drag surface and excludes window actions from it', async () => {
    render(<App bridge={createStaticBridge(createChromeState())} />)

    const chrome = await screen.findByTestId('window-chrome')
    const dragSurface = within(chrome).getByTestId('window-chrome-drag-surface')
    const actions = within(chrome).getByTestId('window-chrome-actions')

    expect(dragSurface).toHaveClass('pywebview-drag-region')
    expect(dragSurface.querySelector('[data-testid="window-chrome-device-name"]')).not.toBeNull()
    expect(actions.closest('.pywebview-drag-region')).toBeNull()
  })

  it('adds truncation and wrapping hooks for long text while keeping window controls clickable', async () => {
    const longState = createLongTextState()
    const user = userEvent.setup()

    render(<App bridge={createMutableBridge(longState)} />)

    const chrome = await screen.findByTestId('window-chrome')
    const chromeDeviceName = within(chrome).getByTestId('window-chrome-device-name')
    const chromeDeviceMeta = within(chrome).getByTestId('window-chrome-device-meta')

    expect(chromeDeviceName).toHaveClass('text-truncate')
    expect(chromeDeviceName).toHaveAttribute('title', longState.devices[0].name)
    expect(chromeDeviceMeta).toHaveClass('text-truncate')
    expect(chromeDeviceMeta).toHaveAttribute('title', longState.connection.lastErrorMessage)

    const trayTitle = screen.getByTestId('tray-quick-panel-title')
    expect(trayTitle).toHaveClass('text-truncate')
    expect(trayTitle).toHaveAttribute('title', longState.devices[0].name)

    await user.click(within(chrome).getByRole('button', { name: 'Minimize window' }))
    await user.click(within(chrome).getByRole('button', { name: 'Maximize window' }))
    await user.click(within(chrome).getByRole('button', { name: 'Hide window to tray' }))

    await user.click(screen.getByRole('button', { name: 'Devices' }))
    const historyTitle = await screen.findByTestId('device-history-title-device-archived')
    expect(historyTitle).toHaveClass('text-truncate')
    expect(historyTitle).toHaveAttribute('title', longState.deviceHistory[0].name)

    await user.click(screen.getByRole('button', { name: 'Diagnostics' }))
    const supportBundlePath = await screen.findByTestId('diagnostics-support-bundle-path')
    expect(supportBundlePath).toHaveClass('text-wrap-anywhere')
    expect(supportBundlePath).toHaveAttribute(
      'title',
      longState.diagnostics.lastSupportBundlePath,
    )
  })

  it('calls window control bridge actions from custom chrome buttons', async () => {
    const bridge = createMutableBridge(createChromeState())

    render(<App bridge={bridge} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Minimize window' }))
    await userEvent.click(screen.getByRole('button', { name: 'Maximize window' }))
    await userEvent.click(screen.getByRole('button', { name: 'Hide window to tray' }))

    expect(bridge.minimizeWindow).toHaveBeenCalledTimes(1)
    expect(bridge.toggleMaximizeWindow).toHaveBeenCalledTimes(1)
    expect(bridge.closeMainWindow).toHaveBeenCalledTimes(1)
  })

  it('updates shell state when runtime maximize event arrives', async () => {
    const bridge = createMutableBridge(createChromeState())

    render(<App bridge={bridge} />)

    const shell = await screen.findByTestId('window-shell')
    expect(shell).toHaveAttribute('data-window-state', 'normal')

    bridge.emitRuntime({
      bridgeMode: 'native',
      chrome: 'custom',
      isMaximized: true,
      canMinimize: true,
      canMaximize: true,
      canClose: true,
    })

    await waitFor(() => {
      expect(shell).toHaveAttribute('data-window-state', 'maximized')
    })
  })

  it('keeps window controls visible but disabled for unavailable runtime', async () => {
    render(
      <App
        bridge={createStaticBridge(
          createChromeState({
            runtime: {
              bridgeMode: 'unavailable',
              chrome: 'custom',
              isMaximized: false,
              canMinimize: false,
              canMaximize: false,
              canClose: false,
            } as AppState['runtime'],
          }),
        )}
      />,
    )

    const chrome = await screen.findByTestId('window-chrome')
    expect(within(chrome).getByRole('button', { name: 'Minimize window' })).toBeDisabled()
    expect(within(chrome).getByRole('button', { name: 'Maximize window' })).toBeDisabled()
    expect(within(chrome).getByRole('button', { name: 'Hide window to tray' })).toBeDisabled()
  })

  it('binds rule toggles to state changes', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Automation' }))

    const toggle = await screen.findByRole('checkbox', {
      name: 'Auto-connect Office Headset after reappear or abnormal disconnect',
    })

    expect(toggle).toHaveClass('switch-toggle')
    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    expect(toggle).toBeChecked()
  })

  it('switches theme mode from settings', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Preferences' }))
    await userEvent.selectOptions(
      await screen.findByLabelText('Theme mode'),
      'dark',
    )

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    })
  })

  it('renders settings in a vertical stack and themed selects', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Preferences' }))

    const settingsStack = await screen.findByTestId('settings-stack')
    expect(settingsStack).toBeVisible()
    const selectElements = within(settingsStack).getAllByRole('combobox')
    expect(selectElements.length).toBe(3)
    for (const selectElement of selectElements) {
      expect(selectElement).toHaveClass('themed-select')
    }
    expect(
      within(settingsStack).getByRole('checkbox', { name: 'Start with Windows' }),
    ).toHaveClass('switch-toggle')
  })

  it('keeps the connected device visible even when it is not a supported scan candidate', async () => {
    const bridge = createStaticBridge({
      devices: [
        {
          id: 'device-unsupported',
          name: 'Keyboard',
          isConnected: true,
          isConnecting: false,
          isFavorite: false,
          isIgnored: false,
          supportsAudio: false,
          presentInLastScan: false,
          lastSeen: 'Unknown',
          lastResult: 'Connected',
          rule: {
            mode: 'manual',
            autoConnectOnStartup: false,
            autoConnectOnAppear: false,
          },
        },
      ],
      deviceHistory: [],
      prioritizedDeviceIds: ['device-unsupported'],
      recentActivity: [],
      connection: {
        status: 'connected',
        currentDeviceId: 'device-unsupported',
      },
      startup: {
        autostart: false,
        backgroundStart: false,
        delaySeconds: 0,
        reconnectOnNextStart: false,
      },
      ui: {
        themeMode: 'system',
        language: 'zh-CN',
        showAudioOnly: true,
        diagnosticsMode: false,
      },
      notifications: {
        policy: 'failures',
      },
      diagnostics: {
        lastProbe: 'ok',
        probeResult: 'ok',
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
    })

    render(<App bridge={bridge} />)

    expect(await screen.findByText('当前设备: Keyboard')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '设备库' }))
    expect(
      within(screen.getByTestId('workspace-content')).getByRole('heading', {
        name: 'Keyboard',
      }),
    ).toBeVisible()
    expect(await screen.findByText('已连接，当前未在扫描结果中出现')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '自动连接' }))
    expect(await screen.findByText('没有可用于自动连接的音频设备。')).toBeVisible()
  })

  it('ignores quick panel hash and keeps control center route', async () => {
    window.location.hash = '#quick-panel'
    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByRole('button', { name: 'Cockpit' })).toBeVisible()
    expect(
      within(screen.getByTestId('workspace-content')).getByRole('heading', {
        name: 'Connection cockpit',
      }),
    ).toBeVisible()
    expect(screen.queryByText('Loading quick panel…')).not.toBeInTheDocument()
  })

  it('binds overview reconnect toggle to global startup reconnect', async () => {
    const bridge = createMutableBridge(baseState)
    const user = userEvent.setup()

    render(<App bridge={bridge} />)

    const reconnectButton = await screen.findByRole('button', {
      name: 'Reconnect on next start · Off',
    })
    expect(reconnectButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(reconnectButton)

    expect(bridge.setReconnect).toHaveBeenCalledWith(true)
  })

  it('renders a compact device history section on the devices page', async () => {
    const user = userEvent.setup()

    render(<App bridge={createStaticBridge(baseState)} />)

    await user.click(await screen.findByRole('button', { name: 'Devices' }))

    expect(await screen.findByText('Device History')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Archived Receiver' })).toBeVisible()
    expect(screen.getByText('Favorite')).toBeVisible()
    expect(screen.getByText('Auto-connect on reappear')).toBeVisible()
    expect(screen.getByText('1 successful attempts')).toBeVisible()
    expect(screen.getByText('2 failed attempts')).toBeVisible()
  })

  it('calls bridge updateDeviceRule when favorite is toggled', async () => {
    const bridge = createMutableBridge(baseState)
    const user = userEvent.setup()

    render(<App bridge={bridge} />)

    await user.click(await screen.findByRole('button', { name: 'Devices' }))
    await user.click(
      await screen.findByRole('button', {
        name: 'Add Surface Headphones to favorites',
      }),
    )

    expect(bridge.updateDeviceRule).toHaveBeenCalledWith('device-1', {
      isFavorite: true,
    })
    expect(
      await screen.findByRole('button', {
        name: 'Remove Surface Headphones from favorites',
      }),
    ).toBeVisible()
  })

  it('calls bridge reorderDevicePriority from automation controls', async () => {
    const bridge = createMutableBridge(baseState)
    const user = userEvent.setup()

    render(<App bridge={bridge} />)

    await user.click(await screen.findByRole('button', { name: 'Automation' }))
    await user.click(
      await screen.findByRole('button', {
        name: 'Move Studio Speaker up',
      }),
    )

    expect(bridge.reorderDevicePriority).toHaveBeenCalledWith([
      'device-2',
      'device-1',
    ])
  })

  it('explains auto-connect semantics on automation workspace', async () => {
    const user = userEvent.setup()

    render(<App bridge={createMutableBridge(baseState)} />)

    await user.click(await screen.findByRole('button', { name: 'Automation' }))

    expect(
      await screen.findByText('Manual disconnect wins for the current app run'),
    ).toBeVisible()
    expect(
      screen.getByText('Retry after reappear or abnormal disconnect, then stop after first success'),
    ).toBeVisible()
    expect(
      screen.getByText('Manage auto-connect for reappear and abnormal disconnect recovery.'),
    ).toBeVisible()
  })

  it('shows distinct copy for unavailable bridge versus no matched A2DP source', async () => {
    render(
      <App
        bridge={createStaticBridge({
          ...baseState,
          devices: [],
          prioritizedDeviceIds: [],
          runtime: {
            bridgeMode: 'unavailable',
            chrome: 'custom',
            isMaximized: false,
            canMinimize: false,
            canMaximize: false,
            canClose: false,
          },
        })}
      />,
    )

    expect((await screen.findAllByText('Bridge unavailable')).length).toBeGreaterThan(0)
    expect(
      screen.getAllByText('Native desktop bridge is not available in this runtime.')
        .length,
    ).toBeGreaterThan(0)

    render(
      <App
        bridge={createStaticBridge({
          ...baseState,
          devices: [
            {
              ...baseState.devices[0],
              supportsAudio: false,
            },
          ],
          prioritizedDeviceIds: ['device-1'],
        })}
      />,
    )

    expect((await screen.findAllByText('No matched A2DP source devices')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Bridge mode: native').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Total discovered devices: 1').length).toBeGreaterThan(0)
  })

  it('places quick actions above the scrollable workspace content inside cockpit', async () => {
    render(<App bridge={createStaticBridge(baseState)} />)

    const workspace = await screen.findByTestId('workspace-shell')
    const quickActions = within(workspace).getByTestId('workspace-quick-actions')
    const content = within(workspace).getByTestId('workspace-content')

    expect(quickActions).toBeVisible()
    expect(content).toBeVisible()
    expect(workspace.firstElementChild).toBe(quickActions)
  })

  it('shows quick actions only on cockpit', async () => {
    const user = userEvent.setup()

    render(<App bridge={createStaticBridge(baseState)} />)

    expect(await screen.findByTestId('workspace-quick-actions')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Devices' }))
    expect(screen.queryByTestId('workspace-quick-actions')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Automation' }))
    expect(screen.queryByTestId('workspace-quick-actions')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Diagnostics' }))
    expect(screen.queryByTestId('workspace-quick-actions')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Preferences' }))
    expect(screen.queryByTestId('workspace-quick-actions')).not.toBeInTheDocument()
  })

  it('keeps A2DP status compact only on cockpit', async () => {
    const bridge = createStaticBridge({
      ...baseState,
      devices: [
        {
          ...baseState.devices[0],
          supportsAudio: false,
        },
      ],
      prioritizedDeviceIds: ['device-1'],
    })
    const user = userEvent.setup()

    render(<App bridge={bridge} />)

    expect((await screen.findAllByText('No matched A2DP source devices')).length).toBe(1)
    expect(screen.queryByText(/Raw device ID/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Devices' }))
    expect(screen.queryByText('No matched A2DP source devices')).not.toBeInTheDocument()
    expect(screen.queryByText(/Raw device ID/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Automation' }))
    expect(screen.queryByText('No matched A2DP source devices')).not.toBeInTheDocument()
    expect(screen.queryByText(/Raw device ID/i)).not.toBeInTheDocument()
  })

  it('shows detailed A2DP diagnostics only on diagnostics workspace', async () => {
    const user = userEvent.setup()

    render(<App bridge={createStaticBridge(baseState)} />)

    expect(screen.queryByTestId('a2dp-source-status-detailed')).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Diagnostics' }))
    await user.click(screen.getByText('View detailed A2DP diagnostics'))

    const detailedStatus = await screen.findByTestId('a2dp-source-status-detailed')
    expect(detailedStatus).toBeVisible()
    expect(within(detailedStatus).getAllByText(/Raw device ID/i).length).toBeGreaterThan(0)
  })

  it('renders new workspace navigation through i18n in zh-CN', async () => {
    render(
      <App
        bridge={createStaticBridge({
          ...baseState,
          ui: {
            ...baseState.ui,
            language: 'zh-CN',
          },
        })}
      />,
    )

    expect(await screen.findByRole('button', { name: '驾驶舱' })).toBeVisible()
    expect(screen.getByRole('button', { name: '设备库' })).toBeVisible()
    expect(screen.getByRole('button', { name: '自动连接' })).toBeVisible()
    expect(screen.getByRole('button', { name: '诊断支持' })).toBeVisible()
    expect(screen.getByRole('button', { name: '偏好设置' })).toBeVisible()
    expect(screen.getAllByRole('button', { name: '刷新设备' }).length).toBeGreaterThan(0)
  })

  it('moves diagnostics out of preferences into a dedicated workspace', async () => {
    const user = userEvent.setup()

    render(<App bridge={createStaticBridge(baseState)} />)

    await user.click(await screen.findByRole('button', { name: 'Diagnostics' }))
    expect(
      await within(screen.getByTestId('workspace-content')).findByRole('heading', {
        name: 'Support & Diagnostics',
      }),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Export support bundle' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Preferences' }))
    expect(await screen.findByTestId('settings-stack')).toBeVisible()
    expect(screen.queryByText('Support & Diagnostics')).not.toBeInTheDocument()
  })

  it('resolves system theme to dark and calls native title sync', async () => {
    const matchMediaMock = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    vi.stubGlobal('matchMedia', matchMediaMock)

    const bridge = createMutableBridge({
      ...baseState,
      ui: {
        ...baseState.ui,
        themeMode: 'system',
      },
    })

    render(<App bridge={bridge} />)

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    })
    expect(bridge.syncWindowTheme).toHaveBeenCalledWith('dark')
  })
})
