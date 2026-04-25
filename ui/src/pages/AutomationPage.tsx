import type { DeviceViewModel } from '../types'
import { useI18n } from '../i18n'

interface AutomationPageProps {
  devices: DeviceViewModel[]
  onToggleAppearRule: (deviceId: string, enabled: boolean) => void
  onReorderPriority: (deviceIds: string[]) => void
}

export function AutomationPage({
  devices,
  onToggleAppearRule,
  onReorderPriority,
}: AutomationPageProps) {
  const { t } = useI18n()

  const moveDevice = (index: number, direction: -1 | 1) => {
    // 这里直接交换当前顺序中的两个 id，再交给宿主侧统一持久化优先级。
    const nextIndex = index + direction
    if (nextIndex < 0 || nextIndex >= devices.length) {
      return
    }
    const reordered = devices.map((device) => device.id)
    const current = reordered[index]
    reordered[index] = reordered[nextIndex]
    reordered[nextIndex] = current
    onReorderPriority(reordered)
  }

  if (!devices.length) {
    return (
      <section className="page-grid">
        <article className="surface-card compact-card">
          <h3>{t('automation.title')}</h3>
          <p className="muted">{t('automation.empty')}</p>
        </article>
      </section>
    )
  }

  return (
    <section className="page-grid">
      <article className="surface-card">
        <p className="panel-kicker">{t('automation.kicker')}</p>
        <h2>{t('automation.rules')}</h2>
        {/* 说明卡片把自动化规则的适用范围和行为意图一起展示出来。 */}
        <div className="feature-note" data-testid="automation-note">
          <div className="feature-note-header">
            <span className="feature-note-icon" aria-hidden="true">
              ✦
            </span>
            <p className="feature-note-copy">{t('automation.description')}</p>
          </div>
          <div className="feature-note-tags">
            <span className="feature-note-tag">{t('automation.scope')}</span>
            <span className="feature-note-tag">{t('automation.behavior')}</span>
          </div>
        </div>
        <div className="automation-toggle-list">
          {devices.map((device) => (
            <label key={device.id} className="toggle-row">
              <span>{t('automation.appearRule', { name: device.name })}</span>
              <input
                className="switch-toggle"
                type="checkbox"
                aria-label={t('automation.appearRule', { name: device.name })}
                checked={device.rule.autoConnectOnAppear}
                onChange={(event) =>
                  onToggleAppearRule(device.id, event.target.checked)
                }
              />
            </label>
          ))}
        </div>
      </article>

      <article className="surface-card">
        <h3>{t('automation.priority')}</h3>
        {/* 使用上下按钮而非拖拽，保证 WebView 环境与键盘操作都更稳定。 */}
        <ol className="compact-list">
          {devices.map((device, index) => (
            <li key={device.id} className="priority-list-item">
              <span>
                {device.name} {device.isIgnored ? t('automation.ignoredSuffix') : ''}
              </span>
              <button
                type="button"
                className="chip-button priority-button"
                onClick={() => moveDevice(index, -1)}
                disabled={index === 0}
                aria-label={t('automation.moveUp', { name: device.name })}
              >
                ↑
              </button>
              <button
                type="button"
                className="chip-button priority-button"
                onClick={() => moveDevice(index, 1)}
                disabled={index === devices.length - 1}
                aria-label={t('automation.moveDown', { name: device.name })}
              >
                ↓
              </button>
            </li>
          ))}
        </ol>
      </article>
    </section>
  )
}
