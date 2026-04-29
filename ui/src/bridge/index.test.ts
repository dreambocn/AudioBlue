// 锁定 bridge 解析层在 native、mock 与 unavailable 三态下的适配行为。
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
    // listeners 同时收集事件对象与 recordClientEvent 载荷，方便校验桥接双向通道。
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
      recentActivity: [
        {
          id: "evt-2",
          area: "connection",
          eventType: "connection.connected",
          level: "info",
          title: "设备已连接",
          detail: "Desk Speaker 已连接。",
          happenedAt: "2026-03-25T10:05:00+00:00",
        },
      ],
      connectionOverview: {
        status: "connected",
        currentDeviceId: "device-2",
        currentPhase: "connected",
        lastSuccessAt: "2026-03-25T10:05:00+00:00",
      },
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
      runtime: {
        chrome: 'custom',
        isMaximized: true,
        canMinimize: true,
        canMaximize: true,
        canClose: true,
      },
      autoConnectCandidates: ['device-2'],
      diagnostics: {
        databasePath: 'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\audioblue.db',
        logRetentionDays: 90,
        activityEventCount: 3,
        connectionAttemptCount: 2,
        lastSupportBundlePath: 'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\support-bundles\\bundle.zip',
        recentErrors: [],
      },
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
          recentActivity: [
            {
              id: "evt-1",
              area: "connection",
              eventType: "connection.failed",
              level: "error",
              title: "连接失败",
              detail: "Surface Headphones 连接超时。",
              happenedAt: "2026-03-25T10:00:00+00:00",
              deviceId: "device-1",
            },
          ],
          connectionOverview: {
            status: "connected",
            currentDeviceId: "device-1",
            currentPhase: "connected",
            lastSuccessAt: "2026-03-25T09:59:00+00:00",
            lastAttemptAt: "2026-03-25T10:00:00+00:00",
            lastTrigger: "manual",
            lastErrorCode: "connection.timeout",
            lastErrorMessage: "Surface Headphones 连接超时。",
          },
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
          runtime: {
            chrome: 'custom',
            isMaximized: false,
            canMinimize: true,
            canMaximize: true,
            canClose: true,
          },
          autoConnectCandidates: ['device-1'],
          diagnostics: {
            databasePath: 'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\audioblue.db',
            logRetentionDays: 90,
            activityEventCount: 4,
            connectionAttemptCount: 2,
            lastSupportBundlePath: 'C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\support-bundles\\bundle.zip',
            audioRouting: {
              currentDeviceId: 'device-1',
              remoteContainerId: 'container-1',
              remoteAepConnected: true,
              remoteAepPresent: true,
              localRenderId: 'render-1',
              localRenderName: '扬声器',
              localRenderState: 'active',
              audioFlowObserved: true,
              audioFlowPeakMax: 0.42,
              validationPhase: 'audio_flow',
              lastValidatedAt: '2026-03-25T10:00:02+00:00',
              lastRecoverReason: null,
            },
            recentErrors: [
              {
                title: '连接失败',
                detail: 'Surface Headphones 连接超时。',
                happenedAt: '2026-03-25T10:00:00+00:00',
              },
            ],
          },
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
        minimize_window: vi.fn(async () => undefined),
        toggle_maximize_window: vi.fn(async () => undefined),
        close_main_window: vi.fn(async () => undefined),
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
          runtime: {
            chrome: 'custom',
            isMaximized: false,
            canMinimize: true,
            canMaximize: true,
            canClose: true,
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
    await (
      bridge as unknown as {
        minimizeWindow: () => Promise<void>
        toggleMaximizeWindow: () => Promise<void>
        closeMainWindow: () => Promise<void>
      }
    ).minimizeWindow()
    await (
      bridge as unknown as {
        minimizeWindow: () => Promise<void>
        toggleMaximizeWindow: () => Promise<void>
        closeMainWindow: () => Promise<void>
      }
    ).toggleMaximizeWindow()
    await (
      bridge as unknown as {
        minimizeWindow: () => Promise<void>
        toggleMaximizeWindow: () => Promise<void>
        closeMainWindow: () => Promise<void>
      }
    ).closeMainWindow()
    await bridge.setReconnect(true)
    await bridge.syncWindowTheme('dark')
    await bridge.setLanguage('zh-CN')
    window.dispatchEvent(new CustomEvent('audioblue:state', { detail: pushSnapshot }))
    unsubscribe()

    const pywebviewApi = window.pywebview?.api

    expect(state.runtime.bridgeMode).toBe('native')
    expect((state.runtime as unknown as Record<string, unknown>).chrome).toBe('custom')
    expect((state.runtime as unknown as Record<string, unknown>).isMaximized).toBe(false)
    expect(state.ui.language).toBe('en-US')
    expect(state.ui.themeMode).toBe('dark')
    expect(state.recentActivity[0].title).toBe('连接失败')
    expect(state.diagnostics.databasePath).toMatch(/audioblue\.db$/i)
    expect(state.diagnostics.audioRouting?.remoteContainerId).toBe('container-1')
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
    })
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      is_favorite: true,
      is_ignored: true,
    })
    expect(pywebviewApi?.minimize_window).toHaveBeenCalledTimes(1)
    expect(pywebviewApi?.toggle_maximize_window).toHaveBeenCalledTimes(1)
    expect(pywebviewApi?.close_main_window).toHaveBeenCalledTimes(1)
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
        lastSuccessAt: '2026-03-25T10:05:00+00:00',
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
    expect(listeners).toContainEqual({
      type: 'runtime_changed',
      runtime: expect.objectContaining({
        chrome: 'custom',
        isMaximized: true,
      }),
    })
  })

  it('keeps startup auto-connect untouched when toggling reappear rule', async () => {
    const updateDeviceRule = vi.fn(async () => ({
      devices: [],
      deviceRules: {
        'device-1': {
          auto_connect_on_startup: true,
          auto_connect_on_reappear: true,
        },
      },
      settings: {
        notification: { policy: 'failures' },
        startup: { reconnectOnNextStart: false },
        ui: { theme: 'system', language: 'system' },
      },
    }))
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({})),
        update_device_rule: updateDeviceRule,
      },
    } as typeof window.pywebview

    const bridge = resolveBridge()

    await bridge.updateDeviceRule('device-1', {
      autoConnectOnAppear: true,
      mode: 'appear',
    })

    expect(updateDeviceRule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
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

  it('maps stale and endpoint-not-ready snapshots into failed UI state', async () => {
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({
          devices: [
            {
              deviceId: 'device-1',
              name: 'Surface Headphones',
              connectionState: 'stale',
              capabilities: {
                supports_audio_playback: true,
              },
              lastConnectionAttempt: {
                trigger: 'recover',
                succeeded: false,
                state: 'endpoint_not_ready',
                failureReason: '首次连接后播放端点仍未就绪。',
                failureCode: 'connection.endpoint_not_ready',
                happenedAt: '2026-04-22T10:00:00+00:00',
              },
            },
          ],
          deviceRules: {},
          lastFailure: {
            deviceId: 'device-1',
            state: 'stale',
            code: 'connection.stale',
            message: 'Windows 仍显示设备已连接，但 AudioBlue 已判定当前连接失活。',
          },
          lastTrigger: 'recover',
          connectionOverview: {
            status: 'stale',
            currentDeviceId: 'device-1',
            currentPhase: 'stale',
            lastAttemptAt: '2026-04-22T10:00:00+00:00',
            lastTrigger: 'recover',
            lastErrorCode: 'connection.stale',
            lastErrorMessage: 'Windows 仍显示设备已连接，但 AudioBlue 已判定当前连接失活。',
          },
          settings: {
            notification: { policy: 'failures' },
            startup: {
              autostart: false,
              runInBackground: false,
              launchDelaySeconds: 3,
              reconnectOnNextStart: true,
            },
            ui: { theme: 'dark', highContrast: false, language: 'zh-CN' },
          },
          autoConnectCandidates: [],
          diagnostics: {
            logRetentionDays: 90,
            activityEventCount: 0,
            connectionAttemptCount: 1,
            logRecordCount: 0,
            recentErrors: [],
          },
          deviceHistory: [],
          recentActivity: [],
        })),
      },
    } as typeof window.pywebview

    const bridge = resolveBridge()
    const state = await bridge.getInitialState()

    expect(state.connection.status).toBe('failed')
    expect(state.connection.currentPhase).toBe('failed')
    expect(state.connection.lastErrorCode).toBe('connection.stale')
    expect(state.devices[0].isConnected).toBe(false)
    expect(state.devices[0].isConnecting).toBe(false)
    expect(state.devices[0].lastResult).toBe('首次连接后播放端点仍未就绪。')
  })

  it('marks history entries offline when the matching device is absent from the latest scan', async () => {
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({
          devices: [
            {
              deviceId: 'device-absent',
              name: 'Absent Headset',
              connectionState: 'disconnected',
              presentInLastScan: false,
              capabilities: { supports_audio_playback: true },
            },
          ],
          deviceRules: {},
          deviceHistory: [
            {
              deviceId: 'device-absent',
              name: 'Absent Headset',
              supportsAudioPlayback: true,
              lastSeenAt: '2026-04-28T10:00:00+08:00',
            },
          ],
          settings: {
            notification: { policy: 'failures' },
            startup: { reconnectOnNextStart: false },
            ui: { theme: 'system', language: 'system' },
          },
        })),
      },
    } as typeof window.pywebview

    const state = await resolveBridge().getInitialState()

    expect(state.deviceHistory[0].isCurrentlyVisible).toBe(false)
  })

  it('preserves connection.no_audio diagnostics and error code from native snapshot', async () => {
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({
          devices: [
            {
              deviceId: 'device-1',
              name: 'Phone',
              connectionState: 'failed',
              capabilities: {
                supports_audio_playback: true,
              },
              lastConnectionAttempt: {
                trigger: 'recover',
                succeeded: false,
                state: 'failed',
                failureReason: '设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。',
                failureCode: 'connection.no_audio',
                happenedAt: '2026-04-23T10:00:00+00:00',
              },
            },
          ],
          deviceRules: {},
          lastFailure: {
            deviceId: 'device-1',
            state: 'failed',
            code: 'connection.no_audio',
            message: '设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。',
          },
          connectionOverview: {
            status: 'failed',
            currentPhase: 'failed',
            lastErrorCode: 'connection.no_audio',
            lastErrorMessage: '设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。',
          },
          diagnostics: {
            logRetentionDays: 90,
            activityEventCount: 1,
            connectionAttemptCount: 1,
            logRecordCount: 0,
            audioRouting: {
              currentDeviceId: 'device-1',
              remoteContainerId: 'container-1',
              remoteAepConnected: true,
              remoteAepPresent: true,
              localRenderId: 'render-1',
              localRenderName: '扬声器',
              localRenderState: 'active',
              audioFlowObserved: false,
              audioFlowPeakMax: 0,
              validationPhase: 'failed',
              lastValidatedAt: '2026-04-23T10:00:04+00:00',
              lastRecoverReason: 'no_audio',
            },
            recentErrors: [],
          },
          settings: {
            notification: { policy: 'failures' },
            startup: {
              autostart: false,
              runInBackground: false,
              launchDelaySeconds: 3,
              reconnectOnNextStart: true,
            },
            ui: { theme: 'dark', highContrast: false, language: 'zh-CN' },
          },
          autoConnectCandidates: [],
          deviceHistory: [],
          recentActivity: [],
        })),
      },
    } as typeof window.pywebview

    const bridge = resolveBridge()
    const state = await bridge.getInitialState()

    expect(state.connection.status).toBe('failed')
    expect(state.connection.lastErrorCode).toBe('connection.no_audio')
    expect(state.devices[0].lastResult).toBe('设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。')
    expect(state.diagnostics.audioRouting?.audioFlowObserved).toBe(false)
    expect(state.diagnostics.audioRouting?.lastRecoverReason).toBe('no_audio')
  })
})
