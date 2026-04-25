import type { BackendBridge } from './bridge/types'
import { useResolvedBridge } from './bridge/useResolvedBridge'
import './App.css'
import { TrayQuickPanel } from './components/TrayQuickPanel'
import { WindowChrome } from './components/WindowChrome'
import { LanguageProvider, useI18n } from './i18n'
import { AutomationPage } from './pages/AutomationPage'
import { CockpitPage } from './pages/CockpitPage'
import { DevicesPage } from './pages/DevicesPage'
import { DiagnosticsPage } from './pages/DiagnosticsPage'
import { PreferencesPage } from './pages/PreferencesPage'
import { useControlCenterModel } from './state/useControlCenterModel'
import type { AppRoute } from './types'

const navItems: { key: AppRoute; labelKey: string; descriptionKey: string }[] = [
  { key: 'cockpit', labelKey: 'nav.cockpit', descriptionKey: 'nav.cockpit.description' },
  { key: 'devices', labelKey: 'nav.devices', descriptionKey: 'nav.devices.description' },
  { key: 'automation', labelKey: 'nav.automation', descriptionKey: 'nav.automation.description' },
  {
    key: 'diagnostics',
    labelKey: 'nav.diagnostics',
    descriptionKey: 'nav.diagnostics.description',
  },
  {
    key: 'preferences',
    labelKey: 'nav.preferences',
    descriptionKey: 'nav.preferences.description',
  },
]

interface AppProps {
  bridge?: BackendBridge
}

interface ControlCenterScaffoldProps {
  route: AppRoute
  setRoute: (route: AppRoute) => void
  state: NonNullable<ReturnType<typeof useControlCenterModel>['state']>
  visibleDevices: ReturnType<typeof useControlCenterModel>['visibleDevices']
  audioDevices: ReturnType<typeof useControlCenterModel>['audioDevices']
  activeDevice: ReturnType<typeof useControlCenterModel>['activeDevice']
  cockpitCandidate: ReturnType<typeof useControlCenterModel>['cockpitCandidate']
  sourceAvailability: ReturnType<typeof useControlCenterModel>['sourceAvailability']
  connectDevice: ReturnType<typeof useControlCenterModel>['connectDevice']
  disconnectDevice: ReturnType<typeof useControlCenterModel>['disconnectDevice']
  toggleFavorite: ReturnType<typeof useControlCenterModel>['toggleFavorite']
  toggleAppearRule: ReturnType<typeof useControlCenterModel>['toggleAppearRule']
  reorderPriority: ReturnType<typeof useControlCenterModel>['reorderPriority']
  setTheme: ReturnType<typeof useControlCenterModel>['setTheme']
  setAutostart: ReturnType<typeof useControlCenterModel>['setAutostart']
  setReconnect: ReturnType<typeof useControlCenterModel>['setReconnect']
  setNotificationPolicy: ReturnType<typeof useControlCenterModel>['setNotificationPolicy']
  setLanguage: ReturnType<typeof useControlCenterModel>['setLanguage']
  minimizeWindow: ReturnType<typeof useControlCenterModel>['minimizeWindow']
  toggleMaximizeWindow: ReturnType<typeof useControlCenterModel>['toggleMaximizeWindow']
  closeMainWindow: ReturnType<typeof useControlCenterModel>['closeMainWindow']
  exportDiagnostics: ReturnType<typeof useControlCenterModel>['exportDiagnostics']
  openBluetoothSettings: ReturnType<typeof useControlCenterModel>['openBluetoothSettings']
  refreshDevices: ReturnType<typeof useControlCenterModel>['refreshDevices']
}

function ControlCenterScaffold({
  route,
  setRoute,
  state,
  visibleDevices,
  audioDevices,
  activeDevice,
  cockpitCandidate,
  sourceAvailability,
  connectDevice,
  disconnectDevice,
  toggleFavorite,
  toggleAppearRule,
  reorderPriority,
  setTheme,
  setAutostart,
  setReconnect,
  setNotificationPolicy,
  setLanguage,
  minimizeWindow,
  toggleMaximizeWindow,
  closeMainWindow,
  exportDiagnostics,
  openBluetoothSettings,
  refreshDevices,
}: ControlCenterScaffoldProps) {
  const { t } = useI18n()
  const currentNavItem = navItems.find((item) => item.key === route) ?? navItems[0]
  const currentRouteLabel = t(currentNavItem.labelKey)

  return (
    <div
      className={`window-shell ${state.runtime.isMaximized ? 'is-maximized' : ''}`}
      data-testid="window-shell"
      data-window-state={state.runtime.isMaximized ? 'maximized' : 'normal'}
    >
      <WindowChrome
        route={route}
        routeLabel={currentRouteLabel}
        state={state}
        activeDevice={activeDevice}
        candidateDevice={cockpitCandidate}
        onMinimize={minimizeWindow}
        onToggleMaximize={toggleMaximizeWindow}
        onClose={closeMainWindow}
      />

      <div className="window-body">
        <aside className="sidebar-rail">
          <div className="sidebar-brand surface-panel">
            <div className="sidebar-brand-copy">
              <p className="panel-kicker">AudioBlue</p>
              <h1>{t('app.subtitle')}</h1>
            </div>
            <span className="sidebar-bridge-pill">{state.runtime.bridgeMode}</span>
          </div>

          <nav className="nav-rail" aria-label="Main Navigation">
            {navItems.map((item) => {
              const active = route === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  aria-label={t(item.labelKey)}
                  className={`nav-button ${active ? 'active' : ''}`}
                  onClick={() => setRoute(item.key)}
                >
                  <span className="nav-active-bar" aria-hidden="true" />
                  <span className="nav-label-group">
                    <span className="nav-label">{t(item.labelKey)}</span>
                    <span className="nav-description">{t(item.descriptionKey)}</span>
                  </span>
                </button>
              )
            })}
          </nav>
        </aside>

        <main
          className={`workspace-shell ${route === 'cockpit' ? 'has-quick-actions' : 'single-pane'}`}
          data-testid="workspace-shell"
        >
          {route === 'cockpit' ? (
            <section className="workspace-quick-actions" data-testid="workspace-quick-actions">
              <TrayQuickPanel
                currentDevice={activeDevice}
                reconnectOnNextStart={state.startup.reconnectOnNextStart}
                sourceAvailability={sourceAvailability}
                bridgeMode={state.runtime.bridgeMode}
                totalDevices={state.devices.length}
                matchedSourceDevices={audioDevices}
                debugDevices={state.devices}
                onConnect={connectDevice}
                onDisconnect={disconnectDevice}
                onToggleReconnect={setReconnect}
                onOpenBluetoothSettings={openBluetoothSettings}
                onRefreshDevices={refreshDevices}
              />
            </section>
          ) : null}

          <section className="workspace-content" data-testid="workspace-content">
            <header className="page-header surface-panel">
              <div className="page-header-copy">
                <p className="page-kicker">{t('app.workspaceKicker')}</p>
                <h2>{currentRouteLabel}</h2>
                <p className="page-description">{t(currentNavItem.descriptionKey)}</p>
              </div>
              <div className="page-header-meta">
                <span className={`status-pill ${state.connection.status}`}>
                  {t(`overview.status.${state.connection.currentPhase ?? state.connection.status}`)}
                </span>
                <span className="meta-chip">
                  {t('a2dp.debug.bridgeMode')}: {state.runtime.bridgeMode}
                </span>
              </div>
            </header>

            {route === 'cockpit' ? (
              <CockpitPage
                state={state}
                activeDevice={activeDevice}
                candidateDevice={cockpitCandidate}
                sourceAvailability={sourceAvailability}
                onOpenDiagnostics={() => setRoute('diagnostics')}
              />
            ) : null}

            {route === 'devices' ? (
              <DevicesPage
                devices={visibleDevices}
                deviceHistory={state.deviceHistory ?? []}
                onConnect={connectDevice}
                onDisconnect={disconnectDevice}
                onToggleFavorite={toggleFavorite}
              />
            ) : null}

            {route === 'automation' ? (
              <AutomationPage
                devices={audioDevices}
                onToggleAppearRule={toggleAppearRule}
                onReorderPriority={reorderPriority}
              />
            ) : null}

            {route === 'diagnostics' ? (
              <DiagnosticsPage
                state={state}
                sourceAvailability={sourceAvailability}
                bridgeMode={state.runtime.bridgeMode}
                totalDevices={state.devices.length}
                matchedSourceDevices={audioDevices}
                debugDevices={state.devices}
                onExportDiagnostics={exportDiagnostics}
              />
            ) : null}

            {route === 'preferences' ? (
              <PreferencesPage
                state={state}
                onThemeChange={setTheme}
                onLanguageChange={setLanguage}
                onAutostartChange={setAutostart}
                onNotificationPolicyChange={setNotificationPolicy}
              />
            ) : null}
          </section>
        </main>
      </div>
    </div>
  )
}

function ControlCenterShell({ bridge }: { bridge: BackendBridge }) {
  const {
    route,
    setRoute,
    state,
    isLoading,
    visibleDevices,
    audioDevices,
    activeDevice,
    cockpitCandidate,
    sourceAvailability,
    connectDevice,
    disconnectDevice,
    toggleFavorite,
    toggleAppearRule,
    reorderPriority,
    setTheme,
    setAutostart,
    setReconnect,
    setNotificationPolicy,
    setLanguage,
    minimizeWindow,
    toggleMaximizeWindow,
    closeMainWindow,
    exportDiagnostics,
    openBluetoothSettings,
    refreshDevices,
  } = useControlCenterModel(bridge)

  if (isLoading || !state) {
    return <div className="loading-shell">Loading AudioBlue control center…</div>
  }

  return (
    <LanguageProvider preference={state.ui.language}>
      <ControlCenterScaffold
        route={route}
        setRoute={setRoute}
        state={state}
        visibleDevices={visibleDevices}
        audioDevices={audioDevices}
        activeDevice={activeDevice}
        cockpitCandidate={cockpitCandidate}
        sourceAvailability={sourceAvailability}
        connectDevice={connectDevice}
        disconnectDevice={disconnectDevice}
        toggleFavorite={toggleFavorite}
        toggleAppearRule={toggleAppearRule}
        reorderPriority={reorderPriority}
        setTheme={setTheme}
        setAutostart={setAutostart}
        setReconnect={setReconnect}
        setNotificationPolicy={setNotificationPolicy}
        setLanguage={setLanguage}
        minimizeWindow={minimizeWindow}
        toggleMaximizeWindow={toggleMaximizeWindow}
        closeMainWindow={closeMainWindow}
        exportDiagnostics={exportDiagnostics}
        openBluetoothSettings={openBluetoothSettings}
        refreshDevices={refreshDevices}
      />
    </LanguageProvider>
  )
}

function App({ bridge }: AppProps) {
  const resolvedBridge = useResolvedBridge(bridge)

  return <ControlCenterShell bridge={resolvedBridge} />
}

export default App
