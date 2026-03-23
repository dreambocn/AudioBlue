import { A2dpSourceStatus } from '../components/A2dpSourceStatus'
import type { DeviceViewModel } from '../types'
import { useI18n } from '../i18n'
import type { A2dpSourceAvailability, BridgeMode } from '../types'

interface AutomationPageProps {
  devices: DeviceViewModel[]
  sourceAvailability: A2dpSourceAvailability
  bridgeMode: BridgeMode
  totalDevices: number
  matchedSourceDevices: DeviceViewModel[]
  debugDevices: DeviceViewModel[]
  onToggleAppearRule: (deviceId: string, enabled: boolean) => void
  onReorderPriority: (deviceIds: string[]) => void
}

export function AutomationPage({
  devices,
  sourceAvailability,
  bridgeMode,
  totalDevices,
  matchedSourceDevices,
  debugDevices,
  onToggleAppearRule,
  onReorderPriority,
}: AutomationPageProps) {
  const { t } = useI18n()
  const primaryDevice = devices[0]
  const moveDevice = (index: number, direction: -1 | 1) => {
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

  if (!primaryDevice) {
    return (
      <section className="page-grid">
        <A2dpSourceStatus
          availability={sourceAvailability}
          bridgeMode={bridgeMode}
          totalDevices={totalDevices}
          matchedSourceDevices={matchedSourceDevices}
          debugDevices={debugDevices}
        />
        <article className="surface-card">
          <h2>{t('automation.title')}</h2>
          <p className="muted">{t('automation.empty')}</p>
        </article>
      </section>
    )
  }

  return (
    <section className="page-grid">
      <article className="surface-card">
        <h2>{t('automation.rules')}</h2>
        <p className="muted">{t('automation.description')}</p>
        <label className="toggle-row">
          <span>{t('automation.appearRule')}</span>
          <input
            type="checkbox"
            aria-label={t('automation.appearRule')}
            checked={primaryDevice.rule.autoConnectOnAppear}
            onChange={(event) =>
              onToggleAppearRule(primaryDevice.id, event.target.checked)
            }
          />
        </label>
      </article>

      <A2dpSourceStatus
        availability={sourceAvailability}
        bridgeMode={bridgeMode}
        totalDevices={totalDevices}
        matchedSourceDevices={matchedSourceDevices}
        debugDevices={debugDevices}
      />

      <article className="surface-card">
        <h3>{t('automation.priority')}</h3>
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
