import { useEffect, useState } from 'react'
import { resolveBridge } from '../bridge'
import type { BackendBridge } from '../bridge/types'
import { TrayQuickPanel } from '../components/TrayQuickPanel'
import { LanguageProvider } from '../i18n'
import type { AppState } from '../types'

interface TrayQuickPanelViewProps {
  bridge?: BackendBridge
  onOpenControlCenter?: () => void
}

export function TrayQuickPanelView({
  bridge = resolveBridge(),
  onOpenControlCenter = () => undefined,
}: TrayQuickPanelViewProps) {
  const [state, setState] = useState<AppState | null>(null)

  useEffect(() => {
    let alive = true
    bridge.getInitialState().then((initial) => {
      if (alive) {
        setState(initial)
      }
    })

    const unsub = bridge.onEvent((event) => {
      if (event.type === 'devices_changed') {
        setState((current) => (current ? { ...current, devices: event.devices } : current))
      }
      if (event.type === 'connection_changed') {
        setState((current) =>
          current ? { ...current, connection: event.connection } : current,
        )
      }
    })

    return () => {
      alive = false
      unsub()
    }
  }, [bridge])

  if (!state) {
    return <div className="loading-shell">Loading quick panel…</div>
  }

  const activeDevice = state.devices.find(
    (device) => device.id === state.connection.currentDeviceId,
  )
  const audioDevices = state.devices.filter((device) => device.supportsAudio)
  const sourceAvailability =
    state.runtime.bridgeMode === 'unavailable'
      ? 'unavailable'
      : audioDevices.length === 0
        ? 'no-source'
        : 'available'

  return (
    <LanguageProvider preference={state.ui.language}>
      <TrayQuickPanel
        currentDevice={activeDevice}
        autoConnectEnabled={state.devices.some((device) => device.rule.autoConnectOnAppear)}
        sourceAvailability={sourceAvailability}
        bridgeMode={state.runtime.bridgeMode}
        totalDevices={state.devices.length}
        matchedSourceDevices={audioDevices}
        debugDevices={state.devices}
        onConnect={(id) => bridge.connectDevice(id)}
        onDisconnect={(id) => bridge.disconnectDevice(id)}
        onToggleAutoConnect={(enabled) =>
          activeDevice
            ? bridge.updateDeviceRule(activeDevice.id, {
                autoConnectOnAppear: enabled,
                mode: enabled ? 'appear' : 'manual',
              })
            : Promise.resolve()
        }
        onOpenControlCenter={onOpenControlCenter}
        onOpenBluetoothSettings={() => bridge.openBluetoothSettings()}
      />
    </LanguageProvider>
  )
}
