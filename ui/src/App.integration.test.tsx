import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'
import { createMockBridge } from './bridge/mockBridge'
import type { BackendBridge } from './bridge/types'
import type { AppState } from './types'

afterEach(() => {
  window.location.hash = ''
})

describe('AudioBlue Control Center integration', () => {
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
    async setTheme() {},
    async setLanguage() {},
    async setNotificationPolicy() {},
    async openBluetoothSettings() {},
    async exportDiagnostics() {
      return ''
    },
    onEvent() {
      return () => undefined
    },
  })

  it('renders shell navigation and overview by default', async () => {
    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByRole('button', { name: 'Overview' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Devices' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Automation' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeVisible()
    expect(await screen.findByText('Connection Overview')).toBeVisible()
  })

  it('binds rule toggles to state changes', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Automation' }))

    const toggle = await screen.findByRole('checkbox', {
      name: 'Auto-connect when this device appears',
    })

    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    expect(toggle).toBeChecked()
  })

  it('switches theme mode from settings', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Settings' }))
    await userEvent.selectOptions(
      await screen.findByLabelText('Theme mode'),
      'dark',
    )

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    })
  })

  it('filters unsupported devices and shows empty states', async () => {
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
          lastSeen: 'Unknown',
          lastResult: 'Connected',
          rule: {
            mode: 'manual',
            autoConnectOnStartup: false,
            autoConnectOnAppear: false,
          },
        },
      ],
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
      },
      runtime: {
        bridgeMode: 'native',
      },
    })

    render(<App bridge={bridge} />)

    expect(await screen.findByText('当前设备: 无')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Devices' }))
    expect(await screen.findByText('未发现可用音频设备。')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Automation' }))
    expect(await screen.findByText('没有可自动化的音频设备。')).toBeVisible()
    expect(screen.queryByText('Keyboard')).not.toBeInTheDocument()
  })

  it('ignores quick panel hash and keeps control center route', async () => {
    window.location.hash = '#quick-panel'
    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByRole('button', { name: 'Overview' })).toBeVisible()
    expect(screen.getByText('Connection Overview')).toBeVisible()
    expect(screen.queryByText('Loading quick panel…')).not.toBeInTheDocument()
  })
})
