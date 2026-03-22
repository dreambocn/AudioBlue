import { describe, expect, it, vi, afterEach } from 'vitest'

import { resolveBridge } from './index'
import type { BridgeEvent } from './types'


afterEach(() => {
  delete window.pywebview
  delete window.audioblueBridge
})


describe('resolveBridge', () => {
  it('adapts pywebview api snapshots into UI state and events', async () => {
    const listeners: BridgeEvent[] = []
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
            ui: { theme: 'dark', highContrast: false },
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
            ui: { theme: 'dark', highContrast: false },
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
            ui: { theme: 'dark', highContrast: false },
          },
          autoConnectCandidates: ['device-1'],
        })),
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
    unsubscribe()

    const pywebviewApi = window.pywebview?.api

    expect(state.ui.themeMode).toBe('dark')
    expect(state.devices[0].id).toBe('device-1')
    expect(state.devices[0].rule.mode).toBe('startup')
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
      auto_connect_on_startup: false,
    })
    expect(listeners).toContainEqual({
      type: 'settings_changed',
      settings: expect.objectContaining({
        ui: expect.objectContaining({ themeMode: 'dark' }),
      }),
    })
  })
})
