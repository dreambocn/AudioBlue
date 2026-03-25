// 验证 pywebview 在首屏缺席、稍后注入时的桥接切换行为。
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  delete window.pywebview
  delete window.audioblueBridge
  vi.resetModules()
})

describe('AudioBlue pywebview bridge bootstrap', () => {
  it('switches from unavailable bridge to native bridge when pywebview api becomes ready after initial render', async () => {
    // 先以“桥接不可用”启动，再模拟宿主延迟注入 API。
    delete window.pywebview
    delete window.audioblueBridge
    vi.resetModules()

    const snapshot = {
      devices: [
        {
          deviceId: 'device-1',
          name: 'Surface Headphones',
          connectionState: 'connected',
          presentInLastScan: true,
          capabilities: {
            supports_audio_playback: true,
            supports_microphone: true,
          },
        },
      ],
      deviceRules: {
        'device-1': {
          is_favorite: true,
          priority: 1,
          auto_connect_on_startup: true,
          auto_connect_on_reappear: false,
        },
      },
      lastFailure: null,
      lastTrigger: 'startup',
      settings: {
        notification: { policy: 'failures' },
        startup: {
          autostart: true,
          runInBackground: true,
          launchDelaySeconds: 3,
        },
        ui: {
          theme: 'dark',
          highContrast: false,
          language: 'en-US',
        },
      },
      autoConnectCandidates: ['device-1'],
    }

    const { default: App } = await import('./App')

    render(<App />)

    expect((await screen.findAllByText('Bridge unavailable')).length).toBeGreaterThan(0)

    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => snapshot),
      },
    } as unknown as NonNullable<typeof window.pywebview>

    window.dispatchEvent(new Event('pywebviewready'))

    await waitFor(() => {
      expect(screen.getAllByText(/Surface Headphones/).length).toBeGreaterThan(0)
    })
  })
})
