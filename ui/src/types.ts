export type ThemeMode = 'system' | 'light' | 'dark'
export type NotificationPolicy = 'silent' | 'failures' | 'all'
export type DeviceRuleMode = 'manual' | 'appear'
export type LanguagePreference = 'system' | 'zh-CN' | 'en-US'
export type BridgeMode = 'native' | 'mock' | 'unavailable'

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
  lastSeen: string
  lastConnectionAt?: string
  lastConnectionState?: string
  lastConnectionTrigger?: string
  lastResult: string
  savedRule: DeviceHistorySavedRule
}

export interface ConnectionState {
  status: 'disconnected' | 'connecting' | 'connected'
  currentDeviceId?: string
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

export interface DiagnosticsState {
  lastProbe: string
  probeResult: string
  lastExportPath?: string
}

export interface RuntimeState {
  bridgeMode: BridgeMode
}

export type A2dpSourceAvailability = 'unavailable' | 'no-source' | 'available'

export interface AppState {
  devices: DeviceViewModel[]
  deviceHistory: DeviceHistoryEntry[]
  prioritizedDeviceIds: string[]
  recentActivity: string[]
  connection: ConnectionState
  startup: StartupPreferences
  ui: UiPreferences
  notifications: NotificationPreferences
  diagnostics: DiagnosticsState
  runtime: RuntimeState
}

export type AppRoute = 'overview' | 'devices' | 'automation' | 'settings'
