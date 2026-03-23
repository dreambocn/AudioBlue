import type {
  AppState,
  DeviceRule,
  DeviceRulePatch,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

export type BridgeEvent =
  | { type: 'devices_changed'; devices: AppState['devices'] }
  | { type: 'connection_changed'; connection: AppState['connection'] }
  | { type: 'connection_failed'; message: string }
  | { type: 'rules_changed'; deviceId: string; rule: DeviceRule }
  | { type: 'priorities_changed'; prioritizedDeviceIds: string[] }
  | { type: 'settings_changed'; settings: Pick<AppState, 'startup' | 'ui' | 'notifications'> }
  | { type: 'diagnostics_changed'; diagnostics: AppState['diagnostics'] }

export interface BackendBridge {
  getInitialState(): Promise<AppState>
  refreshDevices(): Promise<AppState['devices']>
  connectDevice(deviceId: string): Promise<void>
  disconnectDevice(deviceId: string): Promise<void>
  updateDeviceRule(deviceId: string, rulePatch: DeviceRulePatch): Promise<void>
  reorderDevicePriority(deviceIds: string[]): Promise<void>
  setAutostart(enabled: boolean): Promise<void>
  setTheme(mode: ThemeMode): Promise<void>
  setLanguage(language: LanguagePreference): Promise<void>
  setNotificationPolicy(policy: NotificationPolicy): Promise<void>
  openBluetoothSettings(): Promise<void>
  exportDiagnostics(): Promise<string>
  onEvent(handler: (event: BridgeEvent) => void): () => void
}
