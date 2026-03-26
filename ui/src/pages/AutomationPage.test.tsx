// 验证自动化页面文案会明确覆盖“再次出现”和“异常断联”两种自动连接场景。
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AutomationPage } from './AutomationPage'
import { LanguageProvider } from '../i18n'

describe('AutomationPage', () => {
  it('describes reappear and abnormal disconnect auto-connect behavior', () => {
    render(
      <LanguageProvider preference="zh-CN">
        <AutomationPage
          devices={[
            {
              id: 'device-1',
              name: 'Headphones',
              isConnected: false,
              isConnecting: false,
              isFavorite: false,
              isIgnored: false,
              supportsAudio: true,
              presentInLastScan: true,
              lastSeen: '刚刚',
              lastResult: '就绪',
              rule: {
                mode: 'manual',
                autoConnectOnStartup: false,
                autoConnectOnAppear: true,
              },
            },
          ]}
          onToggleAppearRule={vi.fn()}
          onReorderPriority={vi.fn()}
        />
      </LanguageProvider>,
    )

    expect(screen.getByText('管理设备再次出现或异常断联后的自动连接与尝试顺序。')).toBeVisible()
    expect(screen.getByText('Headphones 再次出现或异常断联后自动连接')).toBeVisible()
  })
})
