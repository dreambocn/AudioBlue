export type ThemeMode = 'system' | 'light' | 'dark'
export type NotificationPolicy = 'silent' | 'failures' | 'all'
export type DeviceRuleMode = 'manual' | 'startup' | 'appear'

export interface DeviceRule {
  mode: DeviceRuleMode
  autoConnectOnStartup: boolean
  autoConnectOnAppear: boolean
}

export interface DeviceViewModel {
  id: string
  name: string
  isConnected: boolean
  isConnecting: boolean
  isFavorite: boolean
  isIgnored: boolean
  supportsAudio: boolean
  lastSeen: string
  lastResult: string
  rule: DeviceRule
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
}

export interface UiPreferences {
  themeMode: ThemeMode
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

export interface AppState {
  devices: DeviceViewModel[]
  prioritizedDeviceIds: string[]
  recentActivity: string[]
  connection: ConnectionState
  startup: StartupPreferences
  ui: UiPreferences
  notifications: NotificationPreferences
  diagnostics: DiagnosticsState
}

export type AppRoute = 'overview' | 'devices' | 'automation' | 'settings'
