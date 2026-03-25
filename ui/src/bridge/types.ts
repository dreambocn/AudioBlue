import type {
  AppState,
  DeviceRule,
  DeviceRulePatch,
  LanguagePreference,
  NotificationPolicy,
  ThemeMode,
} from '../types'

// 桥接事件是后端向前端主动推送的最小增量集合。
export type BridgeEvent =
  | { type: 'devices_changed'; devices: AppState['devices'] }
  | { type: 'history_changed'; deviceHistory: AppState['deviceHistory'] }
  | { type: 'activity_changed'; recentActivity: AppState['recentActivity'] }
  | { type: 'connection_changed'; connection: AppState['connection'] }
  | { type: 'connection_failed'; message: string }
  | { type: 'rules_changed'; deviceId: string; rule: DeviceRule }
  | { type: 'priorities_changed'; prioritizedDeviceIds: string[] }
  | { type: 'settings_changed'; settings: Pick<AppState, 'startup' | 'ui' | 'notifications'> }
  | { type: 'diagnostics_changed'; diagnostics: AppState['diagnostics'] }

export interface BackendBridge {
  // 所有宿主实现都需要符合这份接口，前端才能在原生桥接与 mock 桥接之间无缝切换。
  getInitialState(): Promise<AppState>
  refreshDevices(): Promise<AppState['devices']>
  connectDevice(deviceId: string): Promise<void>
  disconnectDevice(deviceId: string): Promise<void>
  updateDeviceRule(deviceId: string, rulePatch: DeviceRulePatch): Promise<void>
  reorderDevicePriority(deviceIds: string[]): Promise<void>
  setAutostart(enabled: boolean): Promise<void>
  setReconnect(enabled: boolean): Promise<void>
  setTheme(mode: ThemeMode): Promise<void>
  syncWindowTheme(mode: Exclude<ThemeMode, 'system'>): Promise<void>
  setLanguage(language: LanguagePreference): Promise<void>
  setNotificationPolicy(policy: NotificationPolicy): Promise<void>
  openBluetoothSettings(): Promise<void>
  exportSupportBundle(): Promise<string>
  exportDiagnostics(): Promise<string>
  recordClientEvent(payload: Record<string, unknown>): Promise<void>
  onEvent(handler: (event: BridgeEvent) => void): () => void
}
