import { createMockBridge } from './mockBridge'
import type { BackendBridge, BridgeEvent } from './types'
import type {
  AppState,
  DeviceHistoryEntry,
  DeviceRuleMode,
  DeviceRulePatch,
  LanguagePreference,
  ThemeMode,
} from '../types'

type PyWebviewApi = {
  get_initial_state?: () => Promise<unknown>
  refresh_devices?: () => Promise<unknown>
  connect_device?: (deviceId: string) => Promise<unknown>
  disconnect_device?: (deviceId: string) => Promise<unknown>
  update_device_rule?: (deviceId: string, patch: Record<string, unknown>) => Promise<unknown>
  reorder_device_priority?: (deviceIds: string[]) => Promise<unknown>
  set_autostart?: (enabled: boolean) => Promise<unknown>
  set_reconnect?: (enabled: boolean) => Promise<unknown>
  set_theme?: (mode: string) => Promise<unknown>
  sync_window_theme?: (mode: string) => Promise<unknown>
  set_language?: (language: string) => Promise<unknown>
  set_notification_policy?: (policy: string) => Promise<unknown>
  open_bluetooth_settings?: () => Promise<void>
  export_diagnostics?: () => Promise<string>
}

type RawSnapshot = Record<string, any>

declare global {
  interface Window {
    audioblueBridge?: BackendBridge
    pywebview?: {
      api?: PyWebviewApi
    }
  }
}

const normalizeRule = (rawRule: Record<string, any> | undefined) => {
  const autoConnectOnStartup = Boolean(
    rawRule?.autoConnectOnStartup ?? rawRule?.auto_connect_on_startup,
  )
  const autoConnectOnAppear = Boolean(
    rawRule?.autoConnectOnReappear ?? rawRule?.auto_connect_on_reappear,
  )
  const mode: DeviceRuleMode = autoConnectOnAppear ? 'appear' : 'manual'

  return {
    mode,
    autoConnectOnStartup,
    autoConnectOnAppear,
  }
}

const normalizeHistoryEntry = (rawHistory: Record<string, any>): DeviceHistoryEntry => {
  const rawLastConnectionAt =
    rawHistory.lastConnectionAt ?? rawHistory.last_connection_at
  const lastConnectionState = String(
    rawHistory.lastConnectionState ?? rawHistory.last_connection_state ?? '',
  )
  const rawLastConnectionTrigger =
    rawHistory.lastConnectionTrigger ?? rawHistory.last_connection_trigger
  const lastFailureReason =
    rawHistory.lastFailureReason ?? rawHistory.last_failure_reason
  const rawSavedRule = (rawHistory.savedRule ?? rawHistory.saved_rule ?? {}) as Record<string, any>

  return {
    id: String(rawHistory.deviceId ?? rawHistory.device_id),
    name: String(rawHistory.name ?? rawHistory.deviceId ?? rawHistory.device_id),
    supportsAudio: Boolean(
      rawHistory.supportsAudioPlayback ??
        rawHistory.supports_audio_playback ??
        false,
    ),
    lastSeen:
      rawHistory.lastSeenAt != null
        ? String(rawHistory.lastSeenAt)
        : rawHistory.last_seen_at != null
          ? String(rawHistory.last_seen_at)
          : 'Unknown',
    lastConnectionAt: rawLastConnectionAt != null ? String(rawLastConnectionAt) : undefined,
    lastConnectionState: lastConnectionState || undefined,
    lastConnectionTrigger:
      rawLastConnectionTrigger != null ? String(rawLastConnectionTrigger) : undefined,
    lastResult:
      typeof lastFailureReason === 'string' && lastFailureReason.length > 0
        ? lastFailureReason
        : lastConnectionState === 'connected'
          ? 'Connected'
          : lastConnectionState || 'Previously seen',
    savedRule: {
      isFavorite: Boolean(rawSavedRule.isFavorite ?? rawSavedRule.is_favorite),
      isIgnored: Boolean(rawSavedRule.isIgnored ?? rawSavedRule.is_ignored),
      autoConnectOnAppear: Boolean(
        rawSavedRule.autoConnectOnAppear ??
          rawSavedRule.auto_connect_on_appear ??
          rawSavedRule.autoConnectOnReappear ??
          rawSavedRule.auto_connect_on_reappear,
      ),
      priority:
        typeof rawSavedRule.priority === 'number' ? rawSavedRule.priority : null,
    },
  }
}

const toPythonRulePatch = (rulePatch: DeviceRulePatch) => {
  const nextPatch: Record<string, unknown> = {}

  if ('autoConnectOnStartup' in rulePatch) {
    nextPatch.auto_connect_on_startup = Boolean(rulePatch.autoConnectOnStartup)
  }

  if ('autoConnectOnAppear' in rulePatch) {
    nextPatch.auto_connect_on_reappear = Boolean(rulePatch.autoConnectOnAppear)
  }

  if ('mode' in rulePatch) {
    const mode = String(rulePatch.mode)
    if (!('auto_connect_on_startup' in nextPatch)) {
      nextPatch.auto_connect_on_startup = false
    }
    if (!('auto_connect_on_reappear' in nextPatch)) {
      nextPatch.auto_connect_on_reappear = mode === 'appear'
    }
  }

  if ('isFavorite' in rulePatch) {
    nextPatch.is_favorite = Boolean(rulePatch.isFavorite)
  }

  if ('isIgnored' in rulePatch) {
    nextPatch.is_ignored = Boolean(rulePatch.isIgnored)
  }

  return nextPatch
}

const normalizeSnapshot = (snapshot: RawSnapshot): AppState => {
  const ruleMap = (snapshot.deviceRules ?? {}) as Record<string, Record<string, any>>
  const rawDevices = Array.isArray(snapshot.devices) ? snapshot.devices : []
  const devices = rawDevices.map((device: Record<string, any>) => {
    const rule = normalizeRule(ruleMap[device.deviceId])
    const connectionState = String(device.connectionState ?? 'disconnected')
    const lastAttempt = device.lastConnectionAttempt ?? null
    return {
      id: String(device.deviceId),
      name: String(device.name),
      isConnected: connectionState === 'connected',
      isConnecting: connectionState === 'connecting',
      isFavorite: Boolean(
        ruleMap[device.deviceId]?.isFavorite ?? ruleMap[device.deviceId]?.is_favorite,
      ),
      isIgnored: Boolean(
        ruleMap[device.deviceId]?.isIgnored ?? ruleMap[device.deviceId]?.is_ignored,
      ),
      supportsAudio: Boolean(
        device.capabilities?.supportsAudioPlayback ??
          device.capabilities?.supports_audio_playback ??
          false,
      ),
      presentInLastScan: Boolean(device.presentInLastScan ?? true),
      lastSeen: device.lastSeenAt ? String(device.lastSeenAt) : 'Unknown',
      lastResult:
        lastAttempt?.failureReason ??
        (connectionState === 'connected' ? 'Connected' : 'Ready to connect'),
      rule,
    }
  })
  const rawHistory = Array.isArray(snapshot.deviceHistory ?? snapshot.device_history)
    ? (snapshot.deviceHistory ?? snapshot.device_history)
    : []
  const deviceHistory = rawHistory.map((entry: Record<string, any>) =>
    normalizeHistoryEntry(entry),
  )

  const connectedDevice = devices.find((device) => device.isConnected)
  const prioritizedFromRules = Object.entries(ruleMap)
    .sort(([, left], [, right]) => (left.priority ?? Number.MAX_SAFE_INTEGER) - (right.priority ?? Number.MAX_SAFE_INTEGER))
    .map(([deviceId]) => deviceId)
  const remainingDeviceIds = devices
    .map((device) => device.id)
    .filter((deviceId) => !prioritizedFromRules.includes(deviceId))

  return {
    devices,
    deviceHistory,
    prioritizedDeviceIds: [...prioritizedFromRules, ...remainingDeviceIds],
    recentActivity: snapshot.lastFailure?.message
      ? [String(snapshot.lastFailure.message)]
      : ['Ready to manage Bluetooth audio devices.'],
    connection: {
      status: connectedDevice ? 'connected' : 'disconnected',
      currentDeviceId: connectedDevice?.id,
      lastFailure: snapshot.lastFailure?.message
        ? String(snapshot.lastFailure.message)
        : undefined,
    },
    startup: {
      autostart: Boolean(snapshot.settings?.startup?.autostart),
      backgroundStart: Boolean(snapshot.settings?.startup?.runInBackground),
      delaySeconds: Number(snapshot.settings?.startup?.launchDelaySeconds ?? 0),
      reconnectOnNextStart: Boolean(
        snapshot.settings?.startup?.reconnectOnNextStart ??
          snapshot.settings?.startup?.reconnect_on_next_start ??
          snapshot.reconnect ??
          false,
      ),
    },
    ui: {
      themeMode: String(snapshot.settings?.ui?.theme ?? 'system') as AppState['ui']['themeMode'],
      language: String(snapshot.settings?.ui?.language ?? 'system') as AppState['ui']['language'],
      showAudioOnly: true,
      diagnosticsMode: false,
    },
    notifications: {
      policy: String(snapshot.settings?.notification?.policy ?? 'failures') as AppState['notifications']['policy'],
    },
    diagnostics: {
      lastProbe: 'Desktop bridge connected',
      probeResult: snapshot.lastFailure?.message
        ? 'Recent connection issue captured.'
        : 'No critical warnings.',
    },
    runtime: {
      bridgeMode: 'native',
    },
  }
}

const emitState = (
  state: AppState,
  listeners: Set<(event: BridgeEvent) => void>,
) => {
  listeners.forEach((listener) =>
    listener({ type: 'devices_changed', devices: structuredClone(state.devices) }),
  )
  listeners.forEach((listener) =>
    listener({
      type: 'history_changed',
      deviceHistory: structuredClone(state.deviceHistory),
    }),
  )
  listeners.forEach((listener) =>
    listener({ type: 'connection_changed', connection: structuredClone(state.connection) }),
  )
  listeners.forEach((listener) =>
    listener({
      type: 'priorities_changed',
      prioritizedDeviceIds: structuredClone(state.prioritizedDeviceIds),
    }),
  )
  listeners.forEach((listener) =>
    listener({
      type: 'settings_changed',
      settings: {
        startup: structuredClone(state.startup),
        ui: structuredClone(state.ui),
        notifications: structuredClone(state.notifications),
      },
    }),
  )
  listeners.forEach((listener) =>
    listener({
      type: 'diagnostics_changed',
      diagnostics: structuredClone(state.diagnostics),
    }),
  )
  if (state.connection.lastFailure) {
    listeners.forEach((listener) =>
      listener({ type: 'connection_failed', message: state.connection.lastFailure! }),
    )
  }
}

const createPyWebviewBridge = (api: PyWebviewApi): BackendBridge => {
  const listeners = new Set<(event: BridgeEvent) => void>()

  const applySnapshot = (snapshot: unknown) => {
    const normalized = normalizeSnapshot((snapshot ?? {}) as RawSnapshot)
    emitState(normalized, listeners)
    return normalized
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('audioblue:state', (event: Event) => {
      const customEvent = event as CustomEvent<unknown>
      applySnapshot(customEvent.detail)
    })
  }

  return {
    async getInitialState() {
      return applySnapshot(await api.get_initial_state?.())
    },
    async refreshDevices() {
      return applySnapshot(await api.refresh_devices?.()).devices
    },
    async connectDevice(deviceId) {
      applySnapshot(await api.connect_device?.(deviceId))
    },
    async disconnectDevice(deviceId) {
      applySnapshot(await api.disconnect_device?.(deviceId))
    },
    async updateDeviceRule(deviceId, rulePatch) {
      applySnapshot(await api.update_device_rule?.(deviceId, toPythonRulePatch(rulePatch)))
    },
    async reorderDevicePriority(deviceIds) {
      applySnapshot(await api.reorder_device_priority?.(deviceIds))
    },
    async setAutostart(enabled) {
      applySnapshot(await api.set_autostart?.(enabled))
    },
    async setReconnect(enabled) {
      if (api.set_reconnect) {
        applySnapshot(await api.set_reconnect(enabled))
        return
      }
      const snapshot = (await api.get_initial_state?.()) as RawSnapshot | undefined
      const fallbackSnapshot = {
        ...(snapshot ?? {}),
        settings: {
          ...(snapshot?.settings ?? {}),
          startup: {
            ...(snapshot?.settings?.startup ?? {}),
            reconnectOnNextStart: enabled,
          },
        },
      }
      applySnapshot(fallbackSnapshot)
    },
    async setTheme(mode) {
      applySnapshot(await api.set_theme?.(mode))
    },
    async syncWindowTheme(mode: Exclude<ThemeMode, 'system'>) {
      await api.sync_window_theme?.(mode)
    },
    async setLanguage(language: LanguagePreference) {
      if (api.set_language) {
        applySnapshot(await api.set_language(language))
        return
      }

      const snapshot = (await api.get_initial_state?.()) as RawSnapshot | undefined
      const fallbackSnapshot = {
        ...(snapshot ?? {}),
        settings: {
          ...(snapshot?.settings ?? {}),
          ui: {
            ...(snapshot?.settings?.ui ?? {}),
            language,
          },
        },
      }
      applySnapshot(fallbackSnapshot)
    },
    async setNotificationPolicy(policy) {
      applySnapshot(await api.set_notification_policy?.(policy))
    },
    async openBluetoothSettings() {
      await api.open_bluetooth_settings?.()
    },
    async exportDiagnostics() {
      return (await api.export_diagnostics?.()) ?? ''
    },
    onEvent(handler) {
      listeners.add(handler)
      return () => {
        listeners.delete(handler)
      }
    },
  }
}

const createUnavailableState = (): AppState => ({
  devices: [],
  deviceHistory: [],
  prioritizedDeviceIds: [],
  recentActivity: [],
  connection: {
    status: 'disconnected',
  },
  startup: {
    autostart: false,
    backgroundStart: false,
    delaySeconds: 0,
    reconnectOnNextStart: false,
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
    lastProbe: 'Bridge unavailable',
    probeResult: 'Native desktop bridge is not available in this runtime.',
  },
  runtime: {
    bridgeMode: 'unavailable',
  },
})

const createUnavailableBridge = (): BackendBridge => {
  const listeners = new Set<(event: BridgeEvent) => void>()
  return {
    async getInitialState() {
      return createUnavailableState()
    },
    async refreshDevices() {
      return []
    },
    async connectDevice() {},
    async disconnectDevice() {},
    async updateDeviceRule() {},
    async reorderDevicePriority() {},
    async setAutostart() {},
    async setReconnect() {},
    async setTheme() {},
    async syncWindowTheme() {},
    async setLanguage() {},
    async setNotificationPolicy() {},
    async openBluetoothSettings() {},
    async exportDiagnostics() {
      return ''
    },
    onEvent(handler) {
      listeners.add(handler)
      return () => {
        listeners.delete(handler)
      }
    },
  }
}

export const resolveBridge = (): BackendBridge => {
  if (window.audioblueBridge) {
    return window.audioblueBridge
  }

  if (window.pywebview?.api) {
    return createPyWebviewBridge(window.pywebview.api)
  }

  const isMockEnabled = import.meta.env.DEV && import.meta.env.VITE_AUDIOBLUE_ENABLE_MOCK_BRIDGE === 'true'
  if (isMockEnabled) {
    return createMockBridge()
  }

  return createUnavailableBridge()
}

export * from './types'
