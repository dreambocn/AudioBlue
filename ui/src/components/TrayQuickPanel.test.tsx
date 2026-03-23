import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TrayQuickPanel } from './TrayQuickPanel'
import type { DeviceViewModel } from '../types'

const connectedDevice: DeviceViewModel = {
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
      <TrayQuickPanel
        currentDevice={connectedDevice}
        autoConnectEnabled
        onDisconnect={onDisconnect}
        onConnect={vi.fn()}
        onToggleAutoConnect={vi.fn()}
        onOpenControlCenter={vi.fn()}
        onOpenBluetoothSettings={vi.fn()}
      />,
    )

    expect(screen.getByText('Connected to Galaxy Buds')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(onDisconnect).toHaveBeenCalledWith('device-buds')
  })
})
