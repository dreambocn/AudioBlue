import { useI18n } from '../i18n'
import type { AppRoute, AppState, DeviceViewModel } from '../types'

interface WindowChromeProps {
  route: AppRoute
  routeLabel: string
  state: AppState
  activeDevice?: DeviceViewModel
  candidateDevice?: DeviceViewModel
  onMinimize: () => void
  onToggleMaximize: () => void
  onClose: () => void
}

export function WindowChrome({
  route,
  routeLabel,
  state,
  activeDevice,
  candidateDevice,
  onMinimize,
  onToggleMaximize,
  onClose,
}: WindowChromeProps) {
  const { t } = useI18n()
  const currentDeviceName =
    activeDevice?.name ??
    state.connection.currentDeviceName ??
    candidateDevice?.name ??
    t('common.none')
  const connectionPhase = state.connection.currentPhase ?? state.connection.status
  const connectionLabel = t(`overview.status.${connectionPhase}`)
  const maximizeLabel = state.runtime.isMaximized ? 'Restore window' : 'Maximize window'
  const chromeMetaText = state.connection.lastErrorMessage
    ? state.connection.lastErrorMessage
    : state.runtime.bridgeMode === 'unavailable'
      ? t('a2dp.unavailable.description')
      : t('overview.currentDevice')

  return (
    <header className="window-chrome" data-testid="window-chrome" data-route={route}>
      <div
        className="window-chrome-drag-surface pywebview-drag-region"
        data-testid="window-chrome-drag-surface"
      >
        <div className="window-chrome-section window-chrome-left">
          <div className="window-brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="window-brand-copy">
            <strong>AudioBlue</strong>
            <span className="text-truncate" title={routeLabel}>
              {routeLabel}
            </span>
          </div>
        </div>

        <div className="window-chrome-section window-chrome-center">
          <span className={`chrome-connection-pill ${state.connection.status}`}>{connectionLabel}</span>
          <div className="window-chrome-summary">
            <span
              className="chrome-device-name text-truncate"
              data-testid="window-chrome-device-name"
              title={currentDeviceName}
            >
              {currentDeviceName}
            </span>
            <span
              className="chrome-device-meta text-truncate"
              data-testid="window-chrome-device-meta"
              title={chromeMetaText}
            >
              {chromeMetaText}
            </span>
          </div>
        </div>
      </div>

      <div className="window-chrome-section window-chrome-actions" data-testid="window-chrome-actions">
        <button
          type="button"
          className="chrome-button"
          aria-label="Minimize window"
          disabled={!state.runtime.canMinimize}
          onClick={onMinimize}
        >
          <span aria-hidden="true">-</span>
        </button>
        <button
          type="button"
          className="chrome-button"
          aria-label={maximizeLabel}
          disabled={!state.runtime.canMaximize}
          onClick={onToggleMaximize}
        >
          <span aria-hidden="true">{state.runtime.isMaximized ? '◱' : '□'}</span>
        </button>
        <button
          type="button"
          className="chrome-button chrome-button-close"
          aria-label="Hide window to tray"
          disabled={!state.runtime.canClose}
          onClick={onClose}
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </header>
  )
}
