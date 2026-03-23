import { createContext, useContext, useMemo, type ReactNode } from 'react'

export type SupportedLanguage = 'zh-CN' | 'en-US'
export type LanguagePreference = 'system' | SupportedLanguage
type TranslationVariables = Record<string, string | number>

const messages: Record<SupportedLanguage, Record<string, string>> = {
  'zh-CN': {
    'app.subtitle': 'Win11 混合控制中心',
    'loading.controlCenter': '正在加载 AudioBlue 控制中心…',
    'common.none': '无',
    'common.unknown': '未知',
    'common.on': '开启',
    'common.off': '关闭',
    'nav.overview': '总览',
    'nav.devices': '设备',
    'nav.automation': '自动连接',
    'nav.settings': '设置',
    'command.refreshDevices': '刷新设备',
    'overview.title': '连接总览',
    'devices.empty': '未发现可用音频设备。',
    'overview.lastFailure': '最近失败：{message}',
    'overview.noFailure': '最近没有失败记录',
    'overview.recentActivity': '最近活动',
    'devices.title': '音频设备',
    'devices.description': '管理收藏、连接状态和快速连接操作。',
    'devices.history.title': '设备历史',
    'devices.history.description': '查看之前连接过或保存过规则的设备，以及系统会复用的设备规则。',
    'devices.history.empty': '还没有可显示的历史设备。',
    'devices.history.reuse': '相同设备下次出现时，会自动复用这些已保存设置。',
    'devices.history.lastConnection': '最近连接：{value}',
    'devices.history.lastSeen': '最近出现：{value}',
    'devices.history.status.offline': '当前未在线',
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
    'automation.description': '管理设备再次出现时的自动连接与尝试顺序。',
    'automation.scope': '不影响手动多设备连接',
    'automation.behavior': '首个成功后停止本轮',
    'automation.appearRule': '{name} 再次出现时自动连接',
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
    'settings.diagnostics': '诊断',
    'settings.diagnostics.export': '导出诊断信息',
    'settings.diagnostics.exportedTo': '已导出到：{path}',
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
    'common.on': 'On',
    'common.off': 'Off',
    'nav.overview': 'Overview',
    'nav.devices': 'Devices',
    'nav.automation': 'Auto Connect',
    'nav.settings': 'Settings',
    'command.refreshDevices': 'Refresh Devices',
    'overview.title': 'Connection Overview',
    'devices.empty': 'No supported audio devices found.',
    'overview.lastFailure': 'Last failure: {message}',
    'overview.noFailure': 'No recent failures',
    'overview.recentActivity': 'Recent Activity',
    'devices.title': 'Audio Devices',
    'devices.description': 'Manage favorites, status and quick connection actions.',
    'devices.history.title': 'Device History',
    'devices.history.description': 'Review remembered devices and the saved rules AudioBlue will reuse for them.',
    'devices.history.empty': 'No remembered devices yet.',
    'devices.history.reuse': 'When this device returns, these saved settings will be reused automatically.',
    'devices.history.lastConnection': 'Last connection: {value}',
    'devices.history.lastSeen': 'Last seen: {value}',
    'devices.history.status.offline': 'Not currently visible',
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
    'automation.description': 'Manage reappear auto-connect and attempt order.',
    'automation.scope': 'Manual multi-device stays available',
    'automation.behavior': 'Stops after first successful auto-connect',
    'automation.appearRule': 'Auto-connect {name} when it appears again',
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
    'settings.diagnostics': 'Diagnostics',
    'settings.diagnostics.export': 'Export diagnostics',
    'settings.diagnostics.exportedTo': 'Exported to: {path}',
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
  if (preference === 'system') {
    return resolveSystemLanguage(systemLanguage)
  }
  return preference
}

interface LanguageProviderProps {
  preference: LanguagePreference
  children: ReactNode
}

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
        return Object.entries(variables).reduce(
          (value, [name, variable]) => value.replaceAll(`{${name}}`, String(variable)),
          template,
        )
      },
    }),
    [catalog, language, preference],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within a LanguageProvider.')
  }
  return context
}
