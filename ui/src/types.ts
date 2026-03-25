export type ThemeMode = 'system' | 'light' | 'dark'
export type NotificationPolicy = 'silent' | 'failures' | 'all'
export type DeviceRuleMode = 'manual' | 'appear'
export type LanguagePreference = 'system' | 'zh-CN' | 'en-US'
export type BridgeMode = 'native' | 'mock' | 'unavailable'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'failed'
export type ActivityLevel = 'info' | 'warning' | 'error'

export interface DeviceRule {
  mode: DeviceRuleMode
  autoConnectOnStartup: boolean
  autoConnectOnAppear: boolean
}

export interface DeviceRulePatch extends Partial<DeviceRule> {
  isFavorite?: boolean
  isIgnored?: boolean
}

export interface DeviceViewModel {
  id: string
  name: string
  isConnected: boolean
  isConnecting: boolean
  isFavorite: boolean
  isIgnored: boolean
  supportsAudio: boolean
  presentInLastScan: boolean
  lastSeen: string
  lastResult: string
  rule: DeviceRule
}

export interface DeviceHistorySavedRule {
  isFavorite: boolean
  isIgnored: boolean
  autoConnectOnAppear: boolean
  priority: number | null
}

export interface DeviceHistoryEntry {
  id: string
  name: string
  supportsAudio: boolean
  firstSeen?: string
  lastSeen: string
  lastConnectionAt?: string
  lastConnectionState?: string
  lastConnectionTrigger?: string
  lastResult: string
  lastSuccessAt?: string
  lastFailureAt?: string
  lastPresentAt?: string
  lastAbsentAt?: string
  lastErrorCode?: string
  lastPresentReason?: string
  lastAbsentReason?: string
  successCount: number
  failureCount: number
  isCurrentlyVisible?: boolean
  savedRule: DeviceHistorySavedRule
}

export interface ActivityEvent {
  id: string
  area: string
  level: ActivityLevel | string
  eventType: string
  title: string
  detail: string
  happenedAt: string
  deviceId?: string
  errorCode?: string
  details?: Record<string, unknown>
}

export interface ConnectionState {
  status: ConnectionStatus
  currentDeviceId?: string
  currentDeviceName?: string
  currentPhase?: string
  lastSuccessAt?: string
  lastAttemptAt?: string
  lastTrigger?: string
  lastErrorCode?: string
  lastErrorMessage?: string
  lastStateChangedAt?: string
  lastFailure?: string
}

export interface StartupPreferences {
  autostart: boolean
  backgroundStart: boolean
  delaySeconds: number
  reconnectOnNextStart: boolean
}

export interface UiPreferences {
  themeMode: ThemeMode
  language: LanguagePreference
  showAudioOnly: boolean
  diagnosticsMode: boolean
}

export interface NotificationPreferences {
  policy: NotificationPolicy
}

export interface DiagnosticsErrorSummary {
  title: string
  detail?: string
  happenedAt?: string
  errorCode?: string
}

export interface WatcherDiagnostics {
  initialEnumerationCompleted: boolean
  startupReconnectCompleted: boolean
  knownDeviceCount: number
  activeConnectionCount: number
  serviceShutdown: boolean
}

export interface DiagnosticsState {
  lastProbe?: string
  probeResult?: string
  databasePath?: string
  storageEngine?: string
  logRetentionDays: number
  activityEventCount: number
  connectionAttemptCount: number
  logRecordCount: number
  lastExportPath?: string
  lastExportAt?: string
  lastSupportBundlePath?: string
  lastSupportBundleAt?: string
  recentErrors: DiagnosticsErrorSummary[]
  runtimeMode?: string
  watcher?: WatcherDiagnostics
}

export interface RuntimeState {
  bridgeMode: BridgeMode
}

export type A2dpSourceAvailability = 'unavailable' | 'no-source' | 'available'

export interface AppState {
  devices: DeviceViewModel[]
  deviceHistory: DeviceHistoryEntry[]
  prioritizedDeviceIds: string[]
  recentActivity: ActivityEvent[]
  connection: ConnectionState
  startup: StartupPreferences
  ui: UiPreferences
  notifications: NotificationPreferences
  diagnostics: DiagnosticsState
  runtime: RuntimeState
}

export type AppRoute = 'overview' | 'devices' | 'automation' | 'settings'
