// 验证设备卡片如何映射连接动作、保留提示与收藏按钮行为。
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DeviceCard } from './DeviceCard'
import { LanguageProvider } from '../i18n'

describe('DeviceCard', () => {
  it('calls connect when the primary action is clicked', async () => {
    const user = userEvent.setup()
    const onConnect = vi.fn()
    const onDisconnect = vi.fn()
    const onToggleFavorite = vi.fn()

    render(
      <LanguageProvider preference="zh-CN">
        <DeviceCard
          device={{
            id: 'device-1',
            name: 'Surface Headphones',
            isConnected: false,
            isConnecting: false,
            isFavorite: false,
            isIgnored: false,
            supportsAudio: true,
            presentInLastScan: true,
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
        />
      </LanguageProvider>,
    )

    await user.click(screen.getByRole('button', { name: /connect|连接/i }))

    expect(onConnect).toHaveBeenCalledWith('device-1')
    expect(onDisconnect).not.toHaveBeenCalled()
  })

  it('shows a retained-device hint when the device is connected but missing from the latest scan', () => {
    render(
      <LanguageProvider preference="zh-CN">
        <DeviceCard
          device={{
            id: 'device-2',
            name: 'Phone',
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
          }}
          onConnect={vi.fn()}
          onDisconnect={vi.fn()}
          onToggleFavorite={vi.fn()}
        />
      </LanguageProvider>,
    )

    expect(screen.getByText('已连接，当前未在扫描结果中出现')).toBeVisible()
  })
})
