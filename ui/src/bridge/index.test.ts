import { describe, expect, it, vi, afterEach } from 'vitest'

import { resolveBridge } from './index'
import type { BridgeEvent } from './types'


afterEach(() => {
  delete window.pywebview
  delete window.audioblueBridge
  vi.unstubAllEnvs()
})


describe('resolveBridge', () => {
  it('adapts pywebview api snapshots into UI state and events', async () => {
    const listeners: BridgeEvent[] = []
    const pushSnapshot = {
      devices: [
        {
          deviceId: 'device-2',
          name: 'Desk Speaker',
          connectionState: 'connected',
          capabilities: {
            supports_audio_playback: true,
          },
        },
      ],
      deviceRules: {},
      lastFailure: null,
      lastTrigger: 'manual',
      settings: {
        notification: { policy: 'all' },
        startup: {
          autostart: false,
          runInBackground: false,
          launchDelaySeconds: 3,
        },
        ui: { theme: 'light', highContrast: false, language: 'zh-CN' },
      },
      autoConnectCandidates: ['device-2'],
    }
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({
          devices: [
            {
              deviceId: 'device-1',
              name: 'Surface Headphones',
              connectionState: 'connected',
              capabilities: {
                supports_audio_playback: true,
                supports_microphone: true,
              },
            },
          ],
          deviceRules: {
            'device-1': {
              isFavorite: true,
              isIgnored: false,
              priority: 1,
              autoConnectOnStartup: true,
              autoConnectOnReappear: false,
            },
          },
          lastFailure: null,
          lastTrigger: 'manual',
          settings: {
            notification: { policy: 'failures' },
            startup: {
              autostart: true,
              runInBackground: true,
              launchDelaySeconds: 5,
            },
            ui: { theme: 'dark', highContrast: false, language: 'en-US' },
          },
          autoConnectCandidates: ['device-1'],
        })),
        set_theme: vi.fn(async () => ({
          devices: [],
          deviceRules: {},
          lastFailure: null,
          lastTrigger: 'manual',
          settings: {
            notification: { policy: 'failures' },
            startup: {
              autostart: true,
              runInBackground: true,
              launchDelaySeconds: 5,
            },
            ui: { theme: 'dark', highContrast: false, language: 'en-US' },
          },
          autoConnectCandidates: [],
        })),
        update_device_rule: vi.fn(async () => ({
          devices: [],
          deviceRules: {
            'device-1': {
              isFavorite: true,
              isIgnored: false,
              priority: 1,
              autoConnectOnStartup: false,
              autoConnectOnReappear: true,
            },
          },
          lastFailure: null,
          lastTrigger: 'manual',
          settings: {
            notification: { policy: 'failures' },
            startup: {
              autostart: true,
              runInBackground: true,
              launchDelaySeconds: 5,
            },
            ui: { theme: 'dark', highContrast: false, language: 'en-US' },
          },
          autoConnectCandidates: ['device-1'],
        })),
        set_language: vi.fn(async () => pushSnapshot),
      },
    } as typeof window.pywebview

    const bridge = resolveBridge()
    const unsubscribe = bridge.onEvent((event) => {
      listeners.push(event)
    })

    const state = await bridge.getInitialState()
    await bridge.setTheme('dark')
    await bridge.updateDeviceRule('device-1', {
      autoConnectOnAppear: true,
      mode: 'appear',
    })
    await bridge.setLanguage('zh-CN')
    window.dispatchEvent(new CustomEvent('audioblue:state', { detail: pushSnapshot }))
    unsubscribe()

    const pywebviewApi = window.pywebview?.api

    expect(state.runtime.bridgeMode).toBe('native')
    expect(state.ui.language).toBe('en-US')
    expect(state.ui.themeMode).toBe('dark')
    expect(state.devices[0].id).toBe('device-1')
    expect(state.devices[0].rule.mode).toBe('startup')
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
      auto_connect_on_startup: false,
    })
    expect(pywebviewApi?.set_language).toHaveBeenCalledWith('zh-CN')
    expect(listeners).toContainEqual({
      type: 'settings_changed',
      settings: expect.objectContaining({
        ui: expect.objectContaining({ language: 'zh-CN' }),
      }),
    })
    expect(listeners).toContainEqual({
      type: 'connection_changed',
      connection: expect.objectContaining({
        status: 'connected',
        currentDeviceId: 'device-2',
      }),
    })
  })

  it('returns unavailable bridge by default when no native bridge is present', async () => {
    const bridge = resolveBridge()
    const state = await bridge.getInitialState()

    expect(state.devices).toEqual([])
    expect(state.connection.status).toBe('disconnected')
    expect(state.runtime.bridgeMode).toBe('unavailable')
  })

  it('uses mock bridge only when explicitly enabled in dev', async () => {
    vi.stubEnv('VITE_AUDIOBLUE_ENABLE_MOCK_BRIDGE', 'true')

    const bridge = resolveBridge()
    const state = await bridge.getInitialState()

    expect(state.devices.length).toBeGreaterThan(0)
    expect(state.runtime.bridgeMode).toBe('mock')
  })
})
