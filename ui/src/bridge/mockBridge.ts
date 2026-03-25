import type { BackendBridge, BridgeEvent } from './types'
import type {
  AppState,
  DeviceViewModel,
  DeviceRulePatch,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

const nowIso = () => new Date().toISOString()

const createInitialState = (): AppState => ({
  devices: [
    {
      id: 'device-office',
      name: 'Office Headset',
      isConnected: false,
      isConnecting: false,
      isFavorite: true,
      isIgnored: false,
      supportsAudio: true,
      presentInLastScan: true,
      lastSeen: '2026-03-25T10:00:00+00:00',
      lastResult: 'Ready to connect',
      rule: {
        mode: 'manual',
        autoConnectOnStartup: false,
        autoConnectOnAppear: false,
      },
    },
    {
      id: 'device-buds',
      name: 'Galaxy Buds',
      isConnected: true,
      isConnecting: false,
      isFavorite: false,
      isIgnored: false,
      supportsAudio: true,
      presentInLastScan: true,
      lastSeen: '2026-03-25T10:05:00+00:00',
      lastResult: 'Connected',
      rule: {
        mode: 'appear',
        autoConnectOnStartup: false,
        autoConnectOnAppear: true,
      },
    },
  ],
  deviceHistory: [
    {
      id: 'device-buds',
      name: 'Galaxy Buds',
      supportsAudio: true,
      firstSeen: '2026-03-20T08:00:00+00:00',
      lastSeen: '2026-03-25T10:05:00+00:00',
      lastConnectionAt: '2026-03-25T10:05:00+00:00',
      lastConnectionState: 'connected',
      lastConnectionTrigger: 'manual',
      lastResult: 'Connected',
      lastSuccessAt: '2026-03-25T10:05:00+00:00',
      successCount: 3,
      failureCount: 0,
      isCurrentlyVisible: true,
      savedRule: {
        isFavorite: false,
        isIgnored: false,
        autoConnectOnAppear: true,
        priority: 1,
      },
    },
    {
      id: 'device-archived',
      name: 'Archived Receiver',
      supportsAudio: true,
      firstSeen: '2026-03-20T08:00:00+00:00',
      lastSeen: '2026-03-22T11:00:00+00:00',
      lastConnectionAt: '2026-03-22T10:55:00+00:00',
      lastConnectionState: 'timeout',
      lastConnectionTrigger: 'startup',
      lastResult: 'Connection timed out before audio could start.',
      lastFailureAt: '2026-03-22T10:55:00+00:00',
      lastAbsentAt: '2026-03-22T11:10:00+00:00',
      lastErrorCode: 'connection.timeout',
      lastAbsentReason: 'removed',
      successCount: 1,
      failureCount: 2,
      isCurrentlyVisible: false,
      savedRule: {
        isFavorite: true,
        isIgnored: false,
        autoConnectOnAppear: true,
        priority: 2,
      },
    },
  ],
  prioritizedDeviceIds: ['device-buds', 'device-office'],
  recentActivity: [
    {
      id: 'evt-2',
      area: 'connection',
      level: 'info',
      eventType: 'connection.connected',
      title: '设备已连接',
      detail: 'Galaxy Buds 已连接。',
      happenedAt: '2026-03-25T10:05:00+00:00',
      deviceId: 'device-buds',
    },
    {
      id: 'evt-1',
      area: 'automation',
      level: 'warning',
      eventType: 'automation.startup_restore.exhausted',
      title: '启动自动重连未命中可用设备',
      detail: '启动阶段没有恢复 Office Headset。',
      happenedAt: '2026-03-25T10:00:00+00:00',
      deviceId: 'device-office',
    },
  ],
  connection: {
    status: 'connected',
    currentDeviceId: 'device-buds',
    currentDeviceName: 'Galaxy Buds',
    currentPhase: 'connected',
    lastSuccessAt: '2026-03-25T10:05:00+00:00',
    lastAttemptAt: '2026-03-25T10:05:00+00:00',
    lastTrigger: 'manual',
  },
  startup: {
    autostart: true,
    backgroundStart: true,
    delaySeconds: 5,
    reconnectOnNextStart: true,
  },
  ui: {
    themeMode: 'system',
    language: 'system',
    showAudioOnly: true,
    diagnosticsMode: false,
  },
  notifications: {
    policy: 'failures',
  },
  diagnostics: {
    lastProbe: 'Mock bridge ready',
    probeResult: 'Mock diagnostics loaded.',
    databasePath: 'C:\\Users\\Public\\AudioBlue\\audioblue.db',
    storageEngine: 'sqlite',
    logRetentionDays: 90,
    activityEventCount: 2,
    connectionAttemptCount: 4,
    logRecordCount: 12,
    recentErrors: [],
    runtimeMode: 'mock',
    watcher: {
      initialEnumerationCompleted: true,
      startupReconnectCompleted: true,
      knownDeviceCount: 2,
      activeConnectionCount: 1,
      serviceShutdown: false,
    },
  },
  runtime: {
    bridgeMode: 'mock',
  },
})

const updateDevice = (
  devices: DeviceViewModel[],
  deviceId: string,
  patch: Partial<DeviceViewModel>,
): DeviceViewModel[] =>
  devices.map((device) => (device.id === deviceId ? { ...device, ...patch } : device))

export const createMockBridge = (): BackendBridge => {
  let state = createInitialState()
  const listeners = new Set<(event: BridgeEvent) => void>()

  const emit = (event: BridgeEvent) => {
    listeners.forEach((listener) => listener(event))
  }

  const emitSettings = () => {
    emit({
      type: 'settings_changed',
      settings: {
        startup: state.startup,
        ui: state.ui,
        notifications: state.notifications,
      },
    })
  }

  const emitHistory = () => {
    emit({
      type: 'history_changed',
      deviceHistory: structuredClone(state.deviceHistory),
    })
  }

  const emitActivity = () => {
    emit({
      type: 'activity_changed',
      recentActivity: structuredClone(state.recentActivity),
    })
  }

  const prependActivity = (
    title: string,
    detail: string,
    level: 'info' | 'warning' | 'error' = 'info',
  ) => {
    state = {
      ...state,
      recentActivity: [
        {
          id: `evt-${Date.now()}`,
          area: 'mock',
          level,
          eventType: 'mock.event',
          title,
          detail,
          happenedAt: nowIso(),
        },
        ...state.recentActivity,
      ],
      diagnostics: {
        ...state.diagnostics,
        activityEventCount: state.diagnostics.activityEventCount + 1,
      },
    }
    emitActivity()
    emit({
      type: 'diagnostics_changed',
      diagnostics: structuredClone(state.diagnostics),
    })
  }

  return {
    async getInitialState() {
      return structuredClone(state)
    },
    async refreshDevices() {
      prependActivity('设备列表已刷新', 'Mock bridge 已刷新设备。')
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      return structuredClone(state.devices)
    },
    async connectDevice(deviceId: string) {
      const currentDevice = state.devices.find((device) => device.id === deviceId)
      state = {
        ...state,
        devices: state.devices.map((device) => ({
          ...device,
          isConnected: device.id === deviceId,
          isConnecting: false,
          lastResult: device.id === deviceId ? 'Connected' : device.lastResult,
        })),
        connection: {
          ...state.connection,
          status: 'connected',
          currentDeviceId: deviceId,
          currentDeviceName: currentDevice?.name,
          currentPhase: 'connected',
          lastSuccessAt: nowIso(),
          lastAttemptAt: nowIso(),
          lastTrigger: 'manual',
        },
      }
      prependActivity('设备已连接', `${currentDevice?.name ?? deviceId} 已连接。`)
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      emit({ type: 'connection_changed', connection: structuredClone(state.connection) })
      emitHistory()
    },
    async disconnectDevice(deviceId: string) {
      const currentDevice = state.devices.find((device) => device.id === deviceId)
      state = {
        ...state,
        devices: updateDevice(state.devices, deviceId, {
          isConnected: false,
          lastResult: 'Disconnected',
        }),
        connection: {
          ...state.connection,
          status: 'disconnected',
          currentDeviceId: undefined,
          currentDeviceName: undefined,
          currentPhase: 'disconnected',
          lastAttemptAt: nowIso(),
          lastTrigger: 'manual',
        },
      }
      prependActivity('连接已断开', `${currentDevice?.name ?? deviceId} 已断开连接。`)
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      emit({ type: 'connection_changed', connection: structuredClone(state.connection) })
      emitHistory()
    },
    async updateDeviceRule(deviceId: string, rulePatch: DeviceRulePatch) {
      state = {
        ...state,
        devices: state.devices.map((device) =>
          device.id === deviceId
            ? {
                ...device,
                isFavorite:
                  typeof rulePatch.isFavorite === 'boolean'
                    ? rulePatch.isFavorite
                    : device.isFavorite,
                isIgnored:
                  typeof rulePatch.isIgnored === 'boolean'
                    ? rulePatch.isIgnored
                    : device.isIgnored,
                rule: {
                  ...device.rule,
                  ...(rulePatch.mode ? { mode: rulePatch.mode } : {}),
                  ...(typeof rulePatch.autoConnectOnStartup === 'boolean'
                    ? { autoConnectOnStartup: rulePatch.autoConnectOnStartup }
                    : {}),
                  ...(typeof rulePatch.autoConnectOnAppear === 'boolean'
                    ? { autoConnectOnAppear: rulePatch.autoConnectOnAppear }
                    : {}),
                },
              }
            : device,
        ),
      }
      const target = state.devices.find((device) => device.id === deviceId)
      if (target) {
        prependActivity('自动连接规则已更新', `${target.name} 的规则已更新。`)
        emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
        emit({
          type: 'rules_changed',
          deviceId,
          rule: structuredClone(target.rule),
        })
      }
    },
    async reorderDevicePriority(deviceIds: string[]) {
      state = {
        ...state,
        prioritizedDeviceIds: [...deviceIds],
      }
      prependActivity('自动连接顺序已更新', 'Mock bridge 已更新设备优先级。')
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      emit({
        type: 'priorities_changed',
        prioritizedDeviceIds: structuredClone(state.prioritizedDeviceIds),
      })
    },
    async setAutostart(enabled: boolean) {
      state = {
        ...state,
        startup: {
          ...state.startup,
          autostart: enabled,
        },
      }
      prependActivity('随 Windows 启动设置已更新', `随 Windows 启动已${enabled ? '开启' : '关闭'}。`)
      emitSettings()
    },
    async setReconnect(enabled: boolean) {
      state = {
        ...state,
        startup: {
          ...state.startup,
          reconnectOnNextStart: enabled,
        },
      }
      prependActivity('启动自动重连设置已更新', `下次启动自动重连已${enabled ? '开启' : '关闭'}。`)
      emitSettings()
    },
    async setTheme(mode: ThemeMode) {
      state = {
        ...state,
        ui: {
          ...state.ui,
          themeMode: mode,
        },
      }
      emitSettings()
    },
    async syncWindowTheme() {},
    async setLanguage(language: LanguagePreference) {
      state = {
        ...state,
        ui: {
          ...state.ui,
          language,
        },
      }
      emitSettings()
    },
    async setNotificationPolicy(policy: NotificationPolicy) {
      state = {
        ...state,
        notifications: {
          policy,
        },
      }
      emitSettings()
    },
    async openBluetoothSettings() {
      prependActivity('已打开蓝牙设置', 'Mock bridge 已模拟打开蓝牙设置。')
    },
    async exportSupportBundle() {
      const path = 'C:\\Users\\Public\\AudioBlue\\support-bundles\\support-bundle.zip'
      state = {
        ...state,
        diagnostics: {
          ...state.diagnostics,
          lastSupportBundlePath: path,
          lastSupportBundleAt: nowIso(),
          lastExportPath: path,
          lastExportAt: nowIso(),
        },
      }
      prependActivity('支持包导出成功', `支持包已导出到 ${path}。`)
      emit({
        type: 'diagnostics_changed',
        diagnostics: structuredClone(state.diagnostics),
      })
      return path
    },
    async exportDiagnostics() {
      return this.exportSupportBundle()
    },
    async recordClientEvent(payload: Record<string, unknown>) {
      prependActivity(
        String(payload.title ?? '界面事件'),
        String(payload.detail ?? ''),
        String(payload.level ?? 'error') === 'warning' ? 'warning' : String(payload.level ?? 'error') === 'info' ? 'info' : 'error',
      )
    },
    onEvent(handler) {
      listeners.add(handler)
      return () => {
        listeners.delete(handler)
      }
    },
  }
}
