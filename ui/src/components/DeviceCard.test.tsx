import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DeviceCard } from './DeviceCard'

describe('DeviceCard', () => {
  it('calls connect when the primary action is clicked', async () => {
    const user = userEvent.setup()
    const onConnect = vi.fn()
    const onDisconnect = vi.fn()
    const onToggleFavorite = vi.fn()

    render(
      <DeviceCard
        device={{
          id: 'device-1',
          name: 'Surface Headphones',
          isConnected: false,
          isConnecting: false,
          isFavorite: false,
          isIgnored: false,
          supportsAudio: true,
          lastSeen: 'Just now',
          lastResult: 'Ready to connect',
          rule: {
            mode: 'manual',
            autoConnectOnStartup: false,
            autoConnectOnAppear: false,
          },
        }}
        onConnect={onConnect}
        onDisconnect={onDisconnect}
        onToggleFavorite={onToggleFavorite}
      />,
    )

    await user.click(screen.getByRole('button', { name: /connect/i }))

    expect(onConnect).toHaveBeenCalledWith('device-1')
    expect(onDisconnect).not.toHaveBeenCalled()
  })
})
