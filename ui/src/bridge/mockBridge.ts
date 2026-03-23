import type { BackendBridge, BridgeEvent } from './types'
import type {
  AppState,
  DeviceViewModel,
  DeviceRule,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

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
      lastSeen: '2m ago',
      lastResult: 'Ready to connect',
      rule: {
        mode: 'startup',
        autoConnectOnStartup: true,
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
      lastSeen: 'now',
      lastResult: 'Connected',
      rule: {
        mode: 'appear',
        autoConnectOnStartup: false,
        autoConnectOnAppear: true,
      },
    },
    {
      id: 'device-speaker',
      name: 'Studio Speaker',
      isConnected: false,
      isConnecting: false,
      isFavorite: false,
      isIgnored: true,
      supportsAudio: true,
      presentInLastScan: true,
      lastSeen: '1h ago',
      lastResult: 'Ignored',
      rule: {
        mode: 'manual',
        autoConnectOnStartup: false,
        autoConnectOnAppear: false,
      },
    },
  ],
  prioritizedDeviceIds: ['device-office', 'device-buds', 'device-speaker'],
  recentActivity: [
    'Galaxy Buds connected successfully.',
    'Office Headset auto-connect delayed by 5s.',
    'Studio Speaker ignored by rule engine.',
  ],
  connection: {
    status: 'connected',
    currentDeviceId: 'device-buds',
  },
  startup: {
    autostart: true,
    backgroundStart: true,
    delaySeconds: 5,
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
    lastProbe: 'Bluetooth service OK',
    probeResult: 'No critical warnings.',
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

  return {
    async getInitialState() {
      return structuredClone(state)
    },
    async refreshDevices() {
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      return structuredClone(state.devices)
    },
    async connectDevice(deviceId: string) {
      state = {
        ...state,
        devices: state.devices.map((device) => ({
          ...device,
          isConnected: device.id === deviceId,
          isConnecting: false,
          lastResult: device.id === deviceId ? 'Connected' : device.lastResult,
        })),
        connection: {
          status: 'connected',
          currentDeviceId: deviceId,
        },
      }
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      emit({ type: 'connection_changed', connection: structuredClone(state.connection) })
    },
    async disconnectDevice(deviceId: string) {
      state = {
        ...state,
        devices: updateDevice(state.devices, deviceId, {
          isConnected: false,
          lastResult: 'Disconnected',
        }),
        connection: {
          status: 'disconnected',
        },
      }
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
      emit({ type: 'connection_changed', connection: structuredClone(state.connection) })
    },
    async updateDeviceRule(deviceId: string, rulePatch: Partial<DeviceRule>) {
      state = {
        ...state,
        devices: state.devices.map((device) =>
          device.id === deviceId
            ? { ...device, rule: { ...device.rule, ...rulePatch } }
            : device,
        ),
      }
      const target = state.devices.find((device) => device.id === deviceId)
      if (target) {
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
      emit({ type: 'devices_changed', devices: structuredClone(state.devices) })
    },
    async setAutostart(enabled: boolean) {
      state = {
        ...state,
        startup: {
          ...state.startup,
          autostart: enabled,
        },
      }
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
      state = {
        ...state,
        recentActivity: ['Opened Windows Bluetooth settings.', ...state.recentActivity],
      }
    },
    async exportDiagnostics() {
      const path = 'C:\\Users\\Public\\AudioBlue\\diagnostics.json'
      state = {
        ...state,
        diagnostics: {
          ...state.diagnostics,
          lastExportPath: path,
        },
      }
      emit({
        type: 'diagnostics_changed',
        diagnostics: structuredClone(state.diagnostics),
      })
      return path
    },
    onEvent(handler) {
      listeners.add(handler)
      return () => {
        listeners.delete(handler)
      }
    },
  }
}
