import { describe, expect, it, vi, afterEach } from 'vitest'

import { resolveBridge } from './index'
import type { BridgeEvent } from './types'


afterEach(() => {
  delete window.pywebview
  delete window.audioblueBridge
  vi.unstubAllEnvs()
})


describe('resolveBridge', () => {
  it('reuses the same bridge instance while the runtime mode is unchanged', () => {
    const unavailableBridge = resolveBridge()

    expect(resolveBridge()).toBe(unavailableBridge)

    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({})),
      },
    } as typeof window.pywebview

    const nativeBridge = resolveBridge()

    expect(nativeBridge).not.toBe(unavailableBridge)
    expect(resolveBridge()).toBe(nativeBridge)
  })

  it('adapts pywebview api snapshots into UI state and events', async () => {
    const listeners: Array<BridgeEvent | Record<string, unknown>> = []
    const pushSnapshot = {
      devices: [
        {
          deviceId: 'device-2',
          name: 'Desk Speaker',
          connectionState: 'connected',
          presentInLastScan: false,
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
          reconnectOnNextStart: false,
        },
        ui: { theme: 'light', highContrast: false, language: 'zh-CN' },
      },
      autoConnectCandidates: ['device-2'],
      deviceHistory: [
        {
          deviceId: 'archived-1',
          name: 'Archived Speaker',
          supportsAudioPlayback: true,
          lastSeenAt: '2026-03-20T12:00:00+00:00',
          lastConnectionAt: '2026-03-20T11:58:00+00:00',
          lastConnectionState: 'timeout',
          lastConnectionTrigger: 'startup',
          lastFailureReason: 'Connection timed out before audio could start.',
          savedRule: {
            isFavorite: true,
            isIgnored: false,
            autoConnectOnReappear: true,
            priority: 2,
          },
        },
      ],
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
              is_favorite: true,
              is_ignored: false,
              priority: 1,
              auto_connect_on_startup: true,
              auto_connect_on_reappear: false,
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
              reconnectOnNextStart: true,
            },
            ui: { theme: 'dark', highContrast: false, language: 'en-US' },
          },
          autoConnectCandidates: ['device-1'],
          deviceHistory: [
            {
              deviceId: 'archived-1',
              name: 'Archived Speaker',
              supportsAudioPlayback: true,
              lastSeenAt: '2026-03-20T12:00:00+00:00',
              lastConnectionAt: '2026-03-20T11:58:00+00:00',
              lastConnectionState: 'timeout',
              lastConnectionTrigger: 'startup',
              lastFailureReason: 'Connection timed out before audio could start.',
              savedRule: {
                isFavorite: true,
                isIgnored: false,
                autoConnectOnReappear: true,
                priority: 2,
              },
            },
          ],
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
              reconnectOnNextStart: true,
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
              reconnectOnNextStart: true,
            },
            ui: { theme: 'dark', highContrast: false, language: 'en-US' },
          },
          autoConnectCandidates: ['device-1'],
        })),
        set_language: vi.fn(async () => pushSnapshot),
        set_reconnect: vi.fn(async () => pushSnapshot),
        sync_window_theme: vi.fn(async () => undefined),
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
    await bridge.updateDeviceRule('device-1', {
      isFavorite: true,
      isIgnored: true,
    })
    await bridge.setReconnect(true)
    await bridge.syncWindowTheme('dark')
    await bridge.setLanguage('zh-CN')
    window.dispatchEvent(new CustomEvent('audioblue:state', { detail: pushSnapshot }))
    unsubscribe()

    const pywebviewApi = window.pywebview?.api

    expect(state.runtime.bridgeMode).toBe('native')
    expect(state.ui.language).toBe('en-US')
    expect(state.ui.themeMode).toBe('dark')
    expect(state.devices[0].id).toBe('device-1')
    expect(state.deviceHistory[0]).toEqual(
      expect.objectContaining({
        id: 'archived-1',
        name: 'Archived Speaker',
        lastResult: 'Connection timed out before audio could start.',
      }),
    )
    expect(state.devices[0].rule.mode).toBe('manual')
    expect(state.startup.reconnectOnNextStart).toBe(true)
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
      auto_connect_on_startup: false,
    })
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      is_favorite: true,
      is_ignored: true,
    })
    expect(pywebviewApi?.set_language).toHaveBeenCalledWith('zh-CN')
    expect(pywebviewApi?.set_reconnect).toHaveBeenCalledWith(true)
    expect(pywebviewApi?.sync_window_theme).toHaveBeenCalledWith('dark')
    expect(state.devices[0].isFavorite).toBe(true)
    expect(state.devices[0].isIgnored).toBe(false)
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
    expect(listeners).toContainEqual({
      type: 'devices_changed',
      devices: expect.arrayContaining([
        expect.objectContaining({
          id: 'device-2',
          presentInLastScan: false,
        }),
      ]),
    })
    expect(listeners).toContainEqual({
      type: 'history_changed',
      deviceHistory: expect.arrayContaining([
        expect.objectContaining({
          id: 'archived-1',
          savedRule: expect.objectContaining({
            autoConnectOnAppear: true,
          }),
        }),
      ]),
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
