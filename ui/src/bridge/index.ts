import { createMockBridge } from './mockBridge'
import type { BackendBridge, BridgeEvent } from './types'
import type {
  ActivityEvent,
  AppState,
  ConnectionState,
  ConnectionStatus,
  DeviceHistoryEntry,
  DeviceRuleMode,
  DeviceRulePatch,
  DiagnosticsErrorSummary,
  DiagnosticsState,
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
  export_support_bundle?: () => Promise<string>
  export_diagnostics?: () => Promise<string>
  record_client_event?: (payload: Record<string, unknown>) => Promise<unknown>
}

type RawRecord = Record<string, unknown>
type RawSnapshot = RawRecord

// 浏览器环境下桥接对象可能由 pywebview 注入，也可能由测试桩提供。
declare global {
  interface Window {
    audioblueBridge?: BackendBridge
    pywebview?: {
      api?: PyWebviewApi
    }
  }
}

// 所有快照入口先收敛成对象，避免后续字段读取时散落判空逻辑。
const asRecord = (value: unknown): RawRecord =>
  typeof value === 'object' && value !== null ? (value as RawRecord) : {}

const asRecordMap = (value: unknown): Record<string, RawRecord> =>
  Object.fromEntries(
    Object.entries(asRecord(value)).map(([key, entry]) => [key, asRecord(entry)]),
  )

const asOptionalString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.length > 0 ? value : undefined

const normalizeBackendConnectionState = (value: unknown): string => {
  const raw = String(value ?? 'disconnected')
  if (raw === 'stale' || raw === 'endpoint_not_ready') {
    return 'failed'
  }
  return raw
}

const getPriority = (rawRule: RawRecord): number =>
  typeof rawRule.priority === 'number' ? rawRule.priority : Number.MAX_SAFE_INTEGER

// 兼容蛇形与驼峰字段，保证后端快照和测试桩都能映射为统一规则结构。
const normalizeRule = (rawRule: RawRecord = {}) => {
  const autoConnectOnStartup = Boolean(
    rawRule.autoConnectOnStartup ?? rawRule.auto_connect_on_startup,
  )
  const autoConnectOnAppear = Boolean(
    rawRule.autoConnectOnReappear ?? rawRule.auto_connect_on_reappear,
  )
  const mode: DeviceRuleMode = autoConnectOnAppear ? 'appear' : 'manual'

  return {
    mode,
    autoConnectOnStartup,
    autoConnectOnAppear,
  }
}

// 设备历史需要同时呈现“历史记录”和“当前是否可见”两个维度，因此这里额外接入可见设备集合。
const normalizeHistoryEntry = (
  rawHistory: RawRecord,
  visibleDeviceIds: Set<string>,
): DeviceHistoryEntry => {
  const rawLastConnectionAt =
    rawHistory.lastConnectionAt ?? rawHistory.last_connection_at
  const lastConnectionState = String(
    rawHistory.lastConnectionState ?? rawHistory.last_connection_state ?? '',
  )
  const rawLastConnectionTrigger =
    rawHistory.lastConnectionTrigger ?? rawHistory.last_connection_trigger
  const lastFailureReason =
    rawHistory.lastFailureReason ?? rawHistory.last_failure_reason
  const rawSavedRule = asRecord(rawHistory.savedRule ?? rawHistory.saved_rule)
  const deviceId = String(rawHistory.deviceId ?? rawHistory.device_id ?? '')

  return {
    id: deviceId,
    name: String(rawHistory.name ?? rawHistory.deviceId ?? rawHistory.device_id),
    supportsAudio: Boolean(
      rawHistory.supportsAudioPlayback ??
        rawHistory.supports_audio_playback ??
        false,
    ),
    firstSeen: asOptionalString(rawHistory.firstSeenAt ?? rawHistory.first_seen_at),
    lastSeen:
      rawHistory.lastSeenAt != null
        ? String(rawHistory.lastSeenAt)
        : rawHistory.last_seen_at != null
          ? String(rawHistory.last_seen_at)
          : 'Unknown',
    lastConnectionAt:
      rawLastConnectionAt != null ? String(rawLastConnectionAt) : undefined,
    lastConnectionState: lastConnectionState || undefined,
    lastConnectionTrigger:
      rawLastConnectionTrigger != null ? String(rawLastConnectionTrigger) : undefined,
    lastResult:
      typeof lastFailureReason === 'string' && lastFailureReason.length > 0
        ? lastFailureReason
        : lastConnectionState === 'connected'
          ? 'Connected'
          : lastConnectionState || 'Previously seen',
    lastSuccessAt: asOptionalString(rawHistory.lastSuccessAt ?? rawHistory.last_success_at),
    lastFailureAt: asOptionalString(rawHistory.lastFailureAt ?? rawHistory.last_failure_at),
    lastPresentAt: asOptionalString(rawHistory.lastPresentAt ?? rawHistory.last_present_at),
    lastAbsentAt: asOptionalString(rawHistory.lastAbsentAt ?? rawHistory.last_absent_at),
    lastErrorCode: asOptionalString(rawHistory.lastErrorCode ?? rawHistory.last_error_code),
    lastPresentReason: asOptionalString(
      rawHistory.lastPresentReason ?? rawHistory.last_present_reason,
    ),
    lastAbsentReason: asOptionalString(
      rawHistory.lastAbsentReason ?? rawHistory.last_absent_reason,
    ),
    successCount: Number(rawHistory.successCount ?? rawHistory.success_count ?? 0),
    failureCount: Number(rawHistory.failureCount ?? rawHistory.failure_count ?? 0),
    isCurrentlyVisible: visibleDeviceIds.has(deviceId),
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

// 活动流既要兼容旧字符串日志，也要兼容新结构化事件。
const normalizeActivityEntry = (
  rawEvent: unknown,
  index: number,
): ActivityEvent | null => {
  if (typeof rawEvent === 'string') {
    return {
      id: `legacy-${index}`,
      area: 'runtime',
      level: 'info',
      eventType: 'runtime.note',
      title: rawEvent,
      detail: '',
      happenedAt: '',
    }
  }

  const event = asRecord(rawEvent)
  const title = String(event.title ?? event.message ?? event.eventType ?? event.event_type ?? '').trim()
  if (!title) {
    return null
  }

  return {
    id: String(event.id ?? `event-${index}`),
    area: String(event.area ?? 'runtime'),
    level: String(event.level ?? 'info'),
    eventType: String(event.eventType ?? event.event_type ?? 'runtime.event'),
    title,
    detail:
      typeof event.detail === 'string'
        ? event.detail
        : typeof event.message === 'string'
          ? event.message
          : '',
    happenedAt: String(event.happenedAt ?? event.happened_at ?? ''),
    deviceId: asOptionalString(event.deviceId ?? event.device_id),
    errorCode: asOptionalString(event.errorCode ?? event.error_code),
    details: typeof event.details === 'object' && event.details !== null
      ? (event.details as Record<string, unknown>)
      : undefined,
  }
}

// 最近错误只保留界面可展示的核心字段，避免把任意负载直接暴露到 UI。
const normalizeRecentErrors = (value: unknown): DiagnosticsErrorSummary[] => {
  if (!Array.isArray(value)) {
    return []
  }

  const errors: DiagnosticsErrorSummary[] = []
  for (const item of value) {
    const raw = asRecord(item)
    const title = asOptionalString(raw.title)
    if (!title) {
      continue
    }
    errors.push({
      title,
      detail: asOptionalString(raw.detail),
      happenedAt: asOptionalString(raw.happenedAt ?? raw.happened_at),
      errorCode: asOptionalString(raw.errorCode ?? raw.error_code),
    })
  }
  return errors
}

// 连接概览优先使用后端提供的 connectionOverview，缺失时再从设备列表回推当前连接设备。
const normalizeConnection = (
  snapshot: RawSnapshot,
  devices: AppState['devices'],
): ConnectionState => {
  const rawConnection = asRecord(snapshot.connectionOverview ?? snapshot.connection)
  const connectedDevice =
    devices.find((device) => device.id === rawConnection.currentDeviceId && device.isConnected) ??
    devices.find((device) => device.isConnected)
  const statusValue = normalizeBackendConnectionState(
    rawConnection.status ?? (connectedDevice ? 'connected' : 'disconnected'),
  )
  const statusSet = new Set<ConnectionStatus>([
    'disconnected',
    'connecting',
    'connected',
    'failed',
  ])
  const status = statusSet.has(statusValue as ConnectionStatus)
    ? (statusValue as ConnectionStatus)
    : 'disconnected'
  const lastErrorMessage = asOptionalString(
    rawConnection.lastErrorMessage ?? rawConnection.lastFailure,
  )
  const currentPhase =
    asOptionalString(normalizeBackendConnectionState(rawConnection.currentPhase)) ??
    (status === 'disconnected' && lastErrorMessage ? 'failed' : status)

  return {
    status,
    currentDeviceId: asOptionalString(rawConnection.currentDeviceId) ?? connectedDevice?.id,
    currentDeviceName:
      asOptionalString(rawConnection.currentDeviceName) ?? connectedDevice?.name,
    currentPhase,
    lastSuccessAt: asOptionalString(rawConnection.lastSuccessAt),
    lastAttemptAt: asOptionalString(rawConnection.lastAttemptAt),
    lastTrigger: asOptionalString(rawConnection.lastTrigger),
    lastErrorCode: asOptionalString(rawConnection.lastErrorCode),
    lastErrorMessage,
    lastStateChangedAt: asOptionalString(rawConnection.lastStateChangedAt),
    lastFailure: lastErrorMessage,
  }
}

const normalizeDiagnostics = (
  rawDiagnostics: RawRecord,
): DiagnosticsState => ({
  lastProbe: asOptionalString(rawDiagnostics.lastProbe),
  probeResult: asOptionalString(rawDiagnostics.probeResult),
  databasePath: asOptionalString(rawDiagnostics.databasePath),
  storageEngine: asOptionalString(rawDiagnostics.storageEngine),
  logRetentionDays: Number(rawDiagnostics.logRetentionDays ?? 90),
  activityEventCount: Number(rawDiagnostics.activityEventCount ?? 0),
  connectionAttemptCount: Number(rawDiagnostics.connectionAttemptCount ?? 0),
  logRecordCount: Number(rawDiagnostics.logRecordCount ?? 0),
  lastExportPath: asOptionalString(rawDiagnostics.lastExportPath),
  lastExportAt: asOptionalString(rawDiagnostics.lastExportAt),
  lastSupportBundlePath: asOptionalString(rawDiagnostics.lastSupportBundlePath),
  lastSupportBundleAt: asOptionalString(rawDiagnostics.lastSupportBundleAt),
  recentErrors: normalizeRecentErrors(rawDiagnostics.recentErrors),
  runtimeMode: asOptionalString(rawDiagnostics.runtimeMode),
  watcher:
    typeof rawDiagnostics.watcher === 'object' && rawDiagnostics.watcher !== null
      ? {
          initialEnumerationCompleted: Boolean(
            asRecord(rawDiagnostics.watcher).initialEnumerationCompleted,
          ),
          startupReconnectCompleted: Boolean(
            asRecord(rawDiagnostics.watcher).startupReconnectCompleted,
          ),
          knownDeviceCount: Number(asRecord(rawDiagnostics.watcher).knownDeviceCount ?? 0),
          activeConnectionCount: Number(
            asRecord(rawDiagnostics.watcher).activeConnectionCount ?? 0,
          ),
          serviceShutdown: Boolean(asRecord(rawDiagnostics.watcher).serviceShutdown),
        }
      : undefined,
  audioRouting:
    typeof rawDiagnostics.audioRouting === 'object' && rawDiagnostics.audioRouting !== null
      ? {
          currentDeviceId: asOptionalString(asRecord(rawDiagnostics.audioRouting).currentDeviceId),
          remoteContainerId: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).remoteContainerId,
          ),
          remoteAepConnected:
            typeof asRecord(rawDiagnostics.audioRouting).remoteAepConnected === 'boolean'
              ? Boolean(asRecord(rawDiagnostics.audioRouting).remoteAepConnected)
              : undefined,
          remoteAepPresent:
            typeof asRecord(rawDiagnostics.audioRouting).remoteAepPresent === 'boolean'
              ? Boolean(asRecord(rawDiagnostics.audioRouting).remoteAepPresent)
              : undefined,
          localRenderId: asOptionalString(asRecord(rawDiagnostics.audioRouting).localRenderId),
          localRenderName: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).localRenderName,
          ),
          localRenderState: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).localRenderState,
          ),
          audioFlowObserved:
            typeof asRecord(rawDiagnostics.audioRouting).audioFlowObserved === 'boolean'
              ? Boolean(asRecord(rawDiagnostics.audioRouting).audioFlowObserved)
              : undefined,
          audioFlowPeakMax:
            typeof asRecord(rawDiagnostics.audioRouting).audioFlowPeakMax === 'number'
              ? Number(asRecord(rawDiagnostics.audioRouting).audioFlowPeakMax)
              : undefined,
          validationPhase: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).validationPhase,
          ),
          lastValidatedAt: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).lastValidatedAt,
          ),
          lastRecoverReason: asOptionalString(
            asRecord(rawDiagnostics.audioRouting).lastRecoverReason,
          ),
        }
      : undefined,
})

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
  const ruleMap = asRecordMap(snapshot.deviceRules ?? snapshot.device_rules)
  const rawDevices = Array.isArray(snapshot.devices) ? snapshot.devices : []
  const settings = asRecord(snapshot.settings)
  const startupSettings = asRecord(settings.startup)
  const uiSettings = asRecord(settings.ui)
  const notificationSettings = asRecord(settings.notification)
  const devices = rawDevices.map((rawDevice) => {
    const device = asRecord(rawDevice)
    const deviceId = String(device.deviceId ?? device.device_id ?? '')
    const rule = normalizeRule(ruleMap[deviceId])
    const rawConnectionState = String(device.connectionState ?? 'disconnected')
    const connectionState = normalizeBackendConnectionState(rawConnectionState)
    const lastAttempt = asRecord(device.lastConnectionAttempt)
    const capabilities = asRecord(device.capabilities)
    const failureReason =
      typeof lastAttempt.failureReason === 'string' ? lastAttempt.failureReason : undefined
    return {
      id: deviceId,
      name: String(device.name),
      isConnected: connectionState === 'connected',
      isConnecting: connectionState === 'connecting',
      isFavorite: Boolean(
        ruleMap[deviceId]?.isFavorite ?? ruleMap[deviceId]?.is_favorite,
      ),
      isIgnored: Boolean(
        ruleMap[deviceId]?.isIgnored ?? ruleMap[deviceId]?.is_ignored,
      ),
      supportsAudio: Boolean(
        capabilities.supportsAudioPlayback ??
          capabilities.supports_audio_playback ??
          false,
      ),
      presentInLastScan: Boolean(device.presentInLastScan ?? true),
      lastSeen: device.lastSeenAt ? String(device.lastSeenAt) : 'Unknown',
      lastResult:
        failureReason ??
        (connectionState === 'connected'
          ? 'Connected'
          : connectionState === 'connecting'
            ? 'Connecting'
            : 'Ready to connect'),
      rule,
    }
  })
  const visibleDeviceIds = new Set(devices.map((device) => device.id))
  const rawHistory = Array.isArray(snapshot.deviceHistory ?? snapshot.device_history)
    ? ((snapshot.deviceHistory ?? snapshot.device_history) as unknown[])
    : []
  const deviceHistory = rawHistory.map((entry) =>
    normalizeHistoryEntry(asRecord(entry), visibleDeviceIds),
  )
  const rawRecentActivity = Array.isArray(snapshot.recentActivity)
    ? snapshot.recentActivity
    : Array.isArray(snapshot.recent_activity)
      ? snapshot.recent_activity
      : []
  const recentActivity = rawRecentActivity
    .map((entry, index) => normalizeActivityEntry(entry, index))
    .filter((entry): entry is ActivityEvent => entry !== null)
  const connection = normalizeConnection(snapshot, devices)

  const prioritizedFromRules = Object.entries(ruleMap)
    .sort(([, left], [, right]) => getPriority(left) - getPriority(right))
    .map(([deviceId]) => deviceId)
  const remainingDeviceIds = devices
    .map((device) => device.id)
    .filter((deviceId) => !prioritizedFromRules.includes(deviceId))

  return {
    devices,
    deviceHistory,
    prioritizedDeviceIds: [...prioritizedFromRules, ...remainingDeviceIds],
    recentActivity,
    connection,
    startup: {
      autostart: Boolean(startupSettings.autostart),
      backgroundStart: Boolean(startupSettings.runInBackground),
      delaySeconds: Number(startupSettings.launchDelaySeconds ?? 0),
      reconnectOnNextStart: Boolean(
        startupSettings.reconnectOnNextStart ??
          startupSettings.reconnect_on_next_start ??
          snapshot.reconnect ??
          false,
      ),
    },
    ui: {
      themeMode: String(uiSettings.theme ?? 'system') as AppState['ui']['themeMode'],
      language: String(uiSettings.language ?? 'system') as AppState['ui']['language'],
      showAudioOnly: true,
      diagnosticsMode: false,
    },
    notifications: {
      policy: String(notificationSettings.policy ?? 'failures') as AppState['notifications']['policy'],
    },
    diagnostics: normalizeDiagnostics(asRecord(snapshot.diagnostics)),
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
    listener({
      type: 'activity_changed',
      recentActivity: structuredClone(state.recentActivity),
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
  const lastFailure = state.connection.lastFailure
  if (lastFailure) {
    listeners.forEach((listener) =>
      listener({ type: 'connection_failed', message: lastFailure }),
    )
  }
}

const bridgeCache: {
  pywebviewApi?: PyWebviewApi
  pywebviewBridge?: BackendBridge
  mockBridge?: BackendBridge
  unavailableBridge?: BackendBridge
} = {}

const createPyWebviewBridge = (api: PyWebviewApi): BackendBridge => {
  const listeners = new Set<(event: BridgeEvent) => void>()

  const applySnapshot = (snapshot: unknown) => {
    const normalized = normalizeSnapshot(asRecord(snapshot))
    emitState(normalized, listeners)
    return normalized
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('audioblue:state', (event: Event) => {
      const customEvent = event as CustomEvent<unknown>
      applySnapshot(customEvent.detail)
    })
  }

  const exportSupportBundle = async () =>
    (await api.export_support_bundle?.()) ?? (await api.export_diagnostics?.()) ?? ''

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
      const snapshot = asRecord(await api.get_initial_state?.())
      const fallbackSnapshot = {
        ...snapshot,
        settings: {
          ...asRecord(snapshot.settings),
          startup: {
            ...asRecord(asRecord(snapshot.settings).startup),
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

      const snapshot = asRecord(await api.get_initial_state?.())
      const fallbackSnapshot = {
        ...snapshot,
        settings: {
          ...asRecord(snapshot.settings),
          ui: {
            ...asRecord(asRecord(snapshot.settings).ui),
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
    async exportSupportBundle() {
      return exportSupportBundle()
    },
    async exportDiagnostics() {
      return exportSupportBundle()
    },
    async recordClientEvent(payload) {
      if (api.record_client_event) {
        applySnapshot(await api.record_client_event(payload))
      }
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
    currentPhase: 'disconnected',
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
    logRetentionDays: 90,
    activityEventCount: 0,
    connectionAttemptCount: 0,
    logRecordCount: 0,
    recentErrors: [],
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
    async exportSupportBundle() {
      return ''
    },
    async exportDiagnostics() {
      return ''
    },
    async recordClientEvent() {},
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
    if (bridgeCache.pywebviewApi !== window.pywebview.api) {
      bridgeCache.pywebviewApi = window.pywebview.api
      bridgeCache.pywebviewBridge = createPyWebviewBridge(window.pywebview.api)
    }
    return bridgeCache.pywebviewBridge!
  }

  const isMockEnabled =
    import.meta.env.DEV && import.meta.env.VITE_AUDIOBLUE_ENABLE_MOCK_BRIDGE === 'true'
  if (isMockEnabled) {
    bridgeCache.mockBridge ??= createMockBridge()
    return bridgeCache.mockBridge
  }

  bridgeCache.unavailableBridge ??= createUnavailableBridge()
  return bridgeCache.unavailableBridge
}

export * from './types'
