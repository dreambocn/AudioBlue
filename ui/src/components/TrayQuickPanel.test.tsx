// 覆盖托盘快速面板在连接态、无活动设备态下的关键交互。
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TrayQuickPanel } from './TrayQuickPanel'
import { LanguageProvider } from '../i18n'
import type { DeviceViewModel } from '../types'

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
})
