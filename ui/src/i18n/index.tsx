import { createContext, useContext, useMemo, type ReactNode } from 'react'

export type SupportedLanguage = 'zh-CN' | 'en-US'
export type LanguagePreference = 'system' | SupportedLanguage
type TranslationVariables = Record<string, string | number>

// 这里只维护核心语言包，页面通过统一键名取词条。
const messages: Record<SupportedLanguage, Record<string, string>> = {
  'zh-CN': {
    'app.subtitle': 'Win11 混合控制中心',
    'loading.controlCenter': '正在加载 AudioBlue 控制中心…',
    'common.none': '无',
    'common.unknown': '未知',
    'common.notAvailable': '暂无',
    'common.on': '开启',
    'common.off': '关闭',
    'nav.overview': '总览',
    'nav.devices': '设备',
    'nav.automation': '自动连接',
    'nav.settings': '设置',
    'command.refreshDevices': '刷新设备',
    'overview.title': '连接总览',
    'overview.status.connected': '已连接',
    'overview.status.connecting': '连接中',
    'overview.status.disconnected': '未连接',
    'overview.status.failed': '连接失败',
    'devices.empty': '未发现可用音频设备。',
    'overview.lastFailure': '最近失败：{message}',
    'overview.noFailure': '最近没有失败记录',
    'overview.noActivity': '最近还没有可展示的活动记录。',
    'overview.recentActivity': '最近活动',
    'overview.lastSuccess': '上次成功',
    'overview.lastAttempt': '最近尝试',
    'overview.lastTrigger': '触发来源',
    'overview.lastErrorCode': '错误代码：{value}',
    'overview.activity.area': '区域：{value}',
    'overview.activity.device': '设备：{value}',
    'overview.activity.code': '代码：{value}',
    'devices.title': '音频设备',
    'devices.description': '管理收藏、连接状态和快速连接操作。',
    'devices.history.title': '设备历史',
    'devices.history.description': '查看设备的出现、连接和失败轨迹，以及系统会复用的规则摘要。',
    'devices.history.empty': '还没有可显示的历史设备。',
    'devices.history.firstSeen': '首次发现：{value}',
    'devices.history.lastConnection': '最近连接：{value}',
    'devices.history.lastSeen': '最近出现：{value}',
    'devices.history.lastSuccess': '最近成功：{value}',
    'devices.history.lastFailure': '最近失败：{value}',
    'devices.history.lastPresent': '最近回归：{value}',
    'devices.history.lastAbsent': '最近离线：{value}',
    'devices.history.successCount': '成功 {value} 次',
    'devices.history.failureCount': '失败 {value} 次',
    'devices.history.reason': '原因：{value}',
    'devices.history.technicalDetails': '查看技术细节',
    'devices.history.status.offline': '当前未在线',
    'devices.history.status.online': '当前在线',
    'devices.history.tag.favorite': '收藏',
    'devices.history.tag.ignored': '忽略',
    'devices.history.tag.reappear': '再次出现时自动连接',
    'devices.history.tag.priority': '自动连接顺序 #{value}',
    'devices.history.tag.none': '暂无已保存设置',
    'devices.retainedHint': '已连接，当前未在扫描结果中出现',
    'device.status.connected': '已连接',
    'device.status.connecting': '连接中…',
    'device.status.available': '可连接',
    'device.favorite.on': '★ 收藏',
    'device.favorite.off': '☆ 收藏',
    'device.favorite.add': '添加 {name} 到收藏',
    'device.favorite.remove': '从收藏中移除 {name}',
    'device.lastSeen': '最近出现：{value}',
    'device.lastResult': '最近结果：{value}',
    'device.action.connect': '连接',
    'device.action.disconnect': '断开连接',
    'automation.title': '自动连接',
    'automation.rules': '自动连接规则',
  'automation.description': '管理设备再次出现或异常断联后的自动连接与尝试顺序。',
  'automation.scope': '手动断开优先，本次运行内不会自动恢复',
  'automation.behavior': '再次出现或异常断联后重试，首个成功后停止本轮',
  'automation.appearRule': '{name} 再次出现或异常断联后自动连接',
    'automation.priority': '自动连接尝试顺序',
    'automation.ignoredSuffix': '（已忽略）',
    'automation.moveUp': '上移 {name}',
    'automation.moveDown': '下移 {name}',
    'automation.empty': '没有可用于自动连接的音频设备。',
    'settings.title': '设置',
    'settings.theme': '主题模式',
    'settings.theme.system': '跟随系统',
    'settings.theme.light': '浅色',
    'settings.theme.dark': '深色',
    'overview.currentDevice': '当前设备',
    'settings.startWithWindows': '随 Windows 启动',
    'settings.notificationPolicy': '通知策略',
    'settings.notification.silent': '静默',
    'settings.notification.failures': '仅失败通知',
    'settings.notification.all': '全部通知',
    'settings.diagnostics': '支持与诊断',
    'settings.diagnostics.export': '导出支持包',
    'settings.diagnostics.exportedTo': '最近支持包：{path}',
    'settings.diagnostics.supportBundleTime': '最近导出时间：{value}',
    'settings.diagnostics.databasePath': '数据库路径：{value}',
    'settings.diagnostics.activityCount': '活动事件',
    'settings.diagnostics.connectionCount': '连接记录',
    'settings.diagnostics.logCount': '日志条数',
    'settings.diagnostics.runtimeMode': '运行模式',
    'settings.diagnostics.technicalDetails': '查看运行诊断',
    'settings.diagnostics.recentErrors': '最近错误',
    'settings.diagnostics.recentErrors.empty': '最近没有新的错误事件。',
    'settings.diagnostics.watcher.enumerationCompleted': '首轮枚举完成：{value}',
    'settings.diagnostics.watcher.startupReconnect': '启动重连阶段完成：{value}',
    'settings.diagnostics.watcher.knownDevices': '当前已知设备数：{value}',
    'settings.diagnostics.watcher.activeConnections': '当前活动连接数：{value}',
    'settings.diagnostics.watcher.serviceShutdown': '连接服务已关闭：{value}',
    'settings.diagnostics.a2dpDetails': '查看详细 A2DP 诊断',
    'settings.updates': '更新',
    'settings.updates.hint': '安装器更新入口预留中。',
    'settings.updates.button': '检查更新（即将支持）',
    'settings.language': '语言',
    'settings.language.system': '跟随系统',
    'settings.language.zh-CN': '中文',
    'settings.language.en-US': 'English',
    'tray.title': '快捷操作',
    'tray.connectedTo': '当前连接到 {name}',
    'tray.noActiveDevice': '当前没有活动音频设备',
    'tray.openControlCenter': '打开控制中心',
    'tray.openBluetoothSettings': '打开蓝牙设置',
    'tray.startupPreference': '启动偏好',
    'tray.reconnectOnNextStart': '下次启动时自动重连',
    'tray.reconnectOnNextStartState': '下次启动时自动重连 · {state}',
    'a2dp.unavailable.title': '桥接不可用',
    'a2dp.unavailable.description': '当前运行环境无法访问原生桌面桥接。',
    'a2dp.noSource.title': '未命中 A2DP Source 设备',
    'a2dp.noSource.description': '桥接已连接，但当前没有可用于本机 A2DP Sink 的远端播放设备。',
    'a2dp.available.title': '已命中 A2DP Source 设备',
    'a2dp.available.description': '已发现可让远端设备把音频播放到本机的候选设备。',
    'a2dp.debug.bridgeMode': '桥接模式',
    'a2dp.debug.totalDevices': '发现设备总数',
    'a2dp.debug.matchedSources': '命中的 A2DP Source 数量',
    'a2dp.debug.deviceId': '原始设备 ID',
    'a2dp.debug.lastSeen': '最近出现',
  },
  'en-US': {
    'app.subtitle': 'Win11 Hybrid Control Center',
    'loading.controlCenter': 'Loading AudioBlue control center…',
    'common.none': 'None',
    'common.unknown': 'Unknown',
    'common.notAvailable': 'N/A',
    'common.on': 'On',
    'common.off': 'Off',
    'nav.overview': 'Overview',
    'nav.devices': 'Devices',
    'nav.automation': 'Auto Connect',
    'nav.settings': 'Settings',
    'command.refreshDevices': 'Refresh Devices',
    'overview.title': 'Connection Overview',
    'overview.status.connected': 'Connected',
    'overview.status.connecting': 'Connecting',
    'overview.status.disconnected': 'Disconnected',
    'overview.status.failed': 'Failed',
    'devices.empty': 'No supported audio devices found.',
    'overview.lastFailure': 'Last failure: {message}',
    'overview.noFailure': 'No recent failures',
    'overview.noActivity': 'No recent activity recorded yet.',
    'overview.recentActivity': 'Recent Activity',
    'overview.lastSuccess': 'Last success',
    'overview.lastAttempt': 'Last attempt',
    'overview.lastTrigger': 'Trigger',
    'overview.lastErrorCode': 'Error code: {value}',
    'overview.activity.area': 'Area: {value}',
    'overview.activity.device': 'Device: {value}',
    'overview.activity.code': 'Code: {value}',
    'devices.title': 'Audio Devices',
    'devices.description': 'Manage favorites, status and quick connection actions.',
    'devices.history.title': 'Device History',
    'devices.history.description': 'Review appearance, connection and failure traces alongside the saved rules AudioBlue will reuse.',
    'devices.history.empty': 'No remembered devices yet.',
    'devices.history.firstSeen': 'First seen: {value}',
    'devices.history.lastConnection': 'Last connection: {value}',
    'devices.history.lastSeen': 'Last seen: {value}',
    'devices.history.lastSuccess': 'Last success: {value}',
    'devices.history.lastFailure': 'Last failure: {value}',
    'devices.history.lastPresent': 'Last reappear: {value}',
    'devices.history.lastAbsent': 'Last disappear: {value}',
    'devices.history.successCount': '{value} successful attempts',
    'devices.history.failureCount': '{value} failed attempts',
    'devices.history.reason': 'Reason: {value}',
    'devices.history.technicalDetails': 'View technical details',
    'devices.history.status.offline': 'Not currently visible',
    'devices.history.status.online': 'Currently visible',
    'devices.history.tag.favorite': 'Favorite',
    'devices.history.tag.ignored': 'Ignored',
    'devices.history.tag.reappear': 'Auto-connect on reappear',
    'devices.history.tag.priority': 'Auto-connect order #{value}',
    'devices.history.tag.none': 'No saved rules yet',
    'devices.retainedHint': 'Connected, but not present in the latest scan.',
    'device.status.connected': 'Connected',
    'device.status.connecting': 'Connecting…',
    'device.status.available': 'Available',
    'device.favorite.on': '★ Favorite',
    'device.favorite.off': '☆ Favorite',
    'device.favorite.add': 'Add {name} to favorites',
    'device.favorite.remove': 'Remove {name} from favorites',
    'device.lastSeen': 'Last seen: {value}',
    'device.lastResult': 'Last result: {value}',
    'device.action.connect': 'Connect',
    'device.action.disconnect': 'Disconnect',
    'automation.title': 'Auto Connect',
    'automation.rules': 'Auto Connect Rules',
  'automation.description': 'Manage auto-connect for reappear and abnormal disconnect recovery.',
  'automation.scope': 'Manual disconnect wins for the current app run',
  'automation.behavior': 'Retry after reappear or abnormal disconnect, then stop after first success',
  'automation.appearRule': 'Auto-connect {name} after reappear or abnormal disconnect',
    'automation.priority': 'Auto-connect Attempt Order',
    'automation.ignoredSuffix': '(Ignored)',
    'automation.moveUp': 'Move {name} up',
    'automation.moveDown': 'Move {name} down',
    'automation.empty': 'No audio devices available for auto-connect.',
    'settings.title': 'Settings',
    'settings.theme': 'Theme mode',
    'settings.theme.system': 'System',
    'settings.theme.light': 'Light',
    'settings.theme.dark': 'Dark',
    'overview.currentDevice': 'Current device',
    'settings.startWithWindows': 'Start with Windows',
    'settings.notificationPolicy': 'Notification policy',
    'settings.notification.silent': 'Silent',
    'settings.notification.failures': 'Only failures',
    'settings.notification.all': 'All notifications',
    'settings.diagnostics': 'Support & Diagnostics',
    'settings.diagnostics.export': 'Export support bundle',
    'settings.diagnostics.exportedTo': 'Latest bundle: {path}',
    'settings.diagnostics.supportBundleTime': 'Last export time: {value}',
    'settings.diagnostics.databasePath': 'Database path: {value}',
    'settings.diagnostics.activityCount': 'Activity events',
    'settings.diagnostics.connectionCount': 'Connection records',
    'settings.diagnostics.logCount': 'Log records',
    'settings.diagnostics.runtimeMode': 'Runtime mode',
    'settings.diagnostics.technicalDetails': 'View runtime diagnostics',
    'settings.diagnostics.recentErrors': 'Recent errors',
    'settings.diagnostics.recentErrors.empty': 'No recent errors recorded.',
    'settings.diagnostics.watcher.enumerationCompleted': 'Initial enumeration completed: {value}',
    'settings.diagnostics.watcher.startupReconnect': 'Startup reconnect phase completed: {value}',
    'settings.diagnostics.watcher.knownDevices': 'Known devices: {value}',
    'settings.diagnostics.watcher.activeConnections': 'Active connections: {value}',
    'settings.diagnostics.watcher.serviceShutdown': 'Service shutdown: {value}',
    'settings.diagnostics.a2dpDetails': 'View detailed A2DP diagnostics',
    'settings.updates': 'Updates',
    'settings.updates.hint': 'Installer-only update channel.',
    'settings.updates.button': 'Check for updates (coming soon)',
    'settings.language': 'Language',
    'settings.language.system': 'System',
    'settings.language.zh-CN': 'Chinese',
    'settings.language.en-US': 'English',
    'tray.title': 'Quick Actions',
    'tray.connectedTo': 'Connected to {name}',
    'tray.noActiveDevice': 'No active audio device',
    'tray.openControlCenter': 'Open Control Center',
    'tray.openBluetoothSettings': 'Open Bluetooth Settings',
    'tray.startupPreference': 'Startup preference',
    'tray.reconnectOnNextStart': 'Reconnect on next start',
    'tray.reconnectOnNextStartState': 'Reconnect on next start · {state}',
    'a2dp.unavailable.title': 'Bridge unavailable',
    'a2dp.unavailable.description': 'Native desktop bridge is not available in this runtime.',
    'a2dp.noSource.title': 'No matched A2DP source devices',
    'a2dp.noSource.description':
      'The bridge is connected, but no remote playback devices currently match this machine as A2DP sink.',
    'a2dp.available.title': 'Matched A2DP source devices',
    'a2dp.available.description':
      'Remote devices that can stream audio to this machine are currently available.',
    'a2dp.debug.bridgeMode': 'Bridge mode',
    'a2dp.debug.totalDevices': 'Total discovered devices',
    'a2dp.debug.matchedSources': 'Matched A2DP source devices',
    'a2dp.debug.deviceId': 'Raw device ID',
    'a2dp.debug.lastSeen': 'Recent seen',
  },
}

interface I18nContextValue {
  language: SupportedLanguage
  preference: LanguagePreference
  t: (key: string, variables?: TranslationVariables) => string
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined)

export function resolveSystemLanguage(rawLanguage?: string): SupportedLanguage {
  const normalized = String(rawLanguage ?? '').toLowerCase()
  if (normalized.startsWith('zh')) {
    return 'zh-CN'
  }
  return 'en-US'
}

export function resolveLanguage(
  preference: LanguagePreference,
  systemLanguage?: string,
): SupportedLanguage {
  // “跟随系统”只在这里解析一次，后续组件统一消费明确语言值。
  if (preference === 'system') {
    return resolveSystemLanguage(systemLanguage)
  }
  return preference
}

interface LanguageProviderProps {
  preference: LanguagePreference
  children: ReactNode
}

// 语言上下文统一处理“跟随系统”逻辑，确保组件只消费已解析结果和翻译函数。
export function LanguageProvider({ preference, children }: LanguageProviderProps) {
  const language = resolveLanguage(preference, globalThis.navigator?.language)
  const catalog = messages[language]
  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      preference,
      t: (key: string, variables?: TranslationVariables) => {
        const template = catalog[key] ?? messages['en-US'][key] ?? key
        if (!variables) {
          return template
        }
        // 简单占位符替换足以覆盖当前文案需求，避免引入额外格式化依赖。
        return Object.entries(variables).reduce(
          (value, [name, variable]) => value.replaceAll(`{${name}}`, String(variable)),
          template,
        )
      },
    }),
    // 语言词条或语言偏好变化时，需要重新生成翻译函数。
    [catalog, language, preference],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    // 开发期直接抛错，便于尽早发现语言上下文缺失问题。
    throw new Error('useI18n must be used within a LanguageProvider.')
  }
  return context
}
