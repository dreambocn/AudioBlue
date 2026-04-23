// 主题模式与通知策略定义了前端呈现与提示的三态边界。
// 这里集中定义前端运行时状态契约，方便 bridge、页面和测试共用同一套类型。
export type ThemeMode = 'system' | 'light' | 'dark'
export type NotificationPolicy = 'silent' | 'failures' | 'all'

// 设备规则模式与语言偏好枚举，用于约束来自桥接的配置 payload。
export type DeviceRuleMode = 'manual' | 'appear'
export type LanguagePreference = 'system' | 'zh-CN' | 'en-US'

// 桥接运行模式与连接状态确保 UI 能区分 native/mock/unavailable 场景。
export type BridgeMode = 'native' | 'mock' | 'unavailable'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'failed'
export type ActivityLevel = 'info' | 'warning' | 'error'

// 设备规则描述单个设备的自动连接策略。
export interface DeviceRule {
  mode: DeviceRuleMode
  autoConnectOnStartup: boolean
  autoConnectOnAppear: boolean
}

// 来自桥接的规则补丁仅包含变化字段。
export interface DeviceRulePatch extends Partial<DeviceRule> {
  // 收藏与忽略不属于 DeviceRule 主体，因此通过补丁字段单独透传。
  isFavorite?: boolean
  isIgnored?: boolean
}

// 前端在连接/历史列表中直接使用的设备快照。
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

// 历史记录中的规则摘要，只需包含决定 auto-connect 的有限字段。
export interface DeviceHistorySavedRule {
  isFavorite: boolean
  isIgnored: boolean
  autoConnectOnAppear: boolean
  priority: number | null
}

// 历史条目用于解释离线设备何时出现、失败和被记录。
export interface DeviceHistoryEntry {
  // 历史记录既承载最近结果，也承载已保存规则，供 Devices 页离线设备卡片展示。
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

// 活动流承载连接/自动化/诊断等级信息。
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

// 当前连接概览及最后一次失败信息，由 bridge 提供。
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

// 启动偏好控制从 Windows 启动到重连等行为。
export interface StartupPreferences {
  autostart: boolean
  backgroundStart: boolean
  delaySeconds: number
  reconnectOnNextStart: boolean
}

// UI 相关偏好同步到主界面。
export interface UiPreferences {
  themeMode: ThemeMode
  language: LanguagePreference
  showAudioOnly: boolean
  diagnosticsMode: boolean
}

// 通知策略用于决定是否展现失败/全部提醒。
export interface NotificationPreferences {
  policy: NotificationPolicy
}

// 诊断错误摘要在 UI 里展示 recentErrors。
export interface DiagnosticsErrorSummary {
  title: string
  detail?: string
  happenedAt?: string
  errorCode?: string
}

// watcher 数据证明设备枚举、重连、连接器状态。
export interface WatcherDiagnostics {
  initialEnumerationCompleted: boolean
  startupReconnectCompleted: boolean
  knownDeviceCount: number
  activeConnectionCount: number
  serviceShutdown: boolean
}

export interface AudioRoutingDiagnostics {
  currentDeviceId?: string
  remoteContainerId?: string
  remoteAepConnected?: boolean
  remoteAepPresent?: boolean
  localRenderId?: string
  localRenderName?: string
  localRenderState?: string
  audioFlowObserved?: boolean
  audioFlowPeakMax?: number
  validationPhase?: string
  lastValidatedAt?: string
  lastRecoverReason?: string
}

// DiagnosticsState 由桥接定期刷新，用于“支持与诊断”页。
export interface DiagnosticsState {
  // 诊断状态既包含数据库统计，也包含运行时桥接和观察器摘要。
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
  audioRouting?: AudioRoutingDiagnostics
}

// runtime 记录桥接运行模式，主要用于托盘的 availability 判断。
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

// AppState 是前端和后台互通的快照契约，桥接通过 getInitialState/事件同步此结构。

// 应用各页的路由枚举，供导航与 Bridge 事件派发等待。
export type AppRoute = 'overview' | 'devices' | 'automation' | 'settings'
