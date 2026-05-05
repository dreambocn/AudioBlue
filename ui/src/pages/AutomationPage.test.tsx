// 验证自动化页面文案会明确覆盖“再次出现”和“异常断联”两种自动连接场景。
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AutomationPage } from './AutomationPage'
import { LanguageProvider } from '../i18n'

describe('AutomationPage', () => {
  const baseDevice = {
    isConnected: false,
    isConnecting: false,
    isFavorite: false,
    isIgnored: false,
    supportsAudio: true,
    presentInLastScan: true,
    lastSeen: '刚刚',
    lastResult: '就绪',
    rule: {
      mode: 'manual' as const,
      autoConnectOnStartup: false,
      autoConnectOnAppear: true,
    },
  }

  it('describes reappear and abnormal disconnect auto-connect behavior', () => {
    render(
      <LanguageProvider preference="zh-CN">
        <AutomationPage
          devices={[
            {
              ...baseDevice,
              id: 'device-1',
              name: 'Headphones',
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

  it('keeps priority move icons grouped after long device names', () => {
    const { container } = render(
      <LanguageProvider preference="zh-CN">
        <AutomationPage
          devices={[
            {
              ...baseDevice,
              id: 'device-1',
              name: '办公室会议室超长名称蓝牙音箱',
            },
            {
              ...baseDevice,
              id: 'device-2',
              name: 'Headphones',
              isIgnored: true,
            },
            {
              ...baseDevice,
              id: 'device-3',
              name: 'Studio Speaker',
            },
          ]}
          onToggleAppearRule={vi.fn()}
          onReorderPriority={vi.fn()}
        />
      </LanguageProvider>,
    )

    const priorityItems = container.querySelectorAll('.priority-list-item')

    expect(priorityItems).toHaveLength(3)
    priorityItems.forEach((item) => {
      // 设备名与操作按钮分列渲染，避免长名称把箭头按钮挤到不同行。
      expect(item.querySelector('.priority-device-name')).not.toBeNull()
      expect(item.querySelector('.priority-actions')).not.toBeNull()
      expect(item.querySelectorAll('.priority-actions .priority-button')).toHaveLength(2)
    })

    expect(screen.getByRole('button', { name: '上移 办公室会议室超长名称蓝牙音箱' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下移 Studio Speaker' })).toBeDisabled()
  })
})
