import type {
  A2dpSourceAvailability,
  AppState,
  ConnectionState,
  DeviceViewModel,
} from '../types'

// 后端返回的是优先列表，这里把优先设备前置，其余设备保留原有顺序。
export const reorderDevicesByPriority = (
  devices: DeviceViewModel[],
  prioritizedDeviceIds: string[],
) => {
  const byId = new Map(devices.map((device) => [device.id, device]))
  const prioritized = prioritizedDeviceIds
    .map((id) => byId.get(id))
    .filter((device): device is DeviceViewModel => Boolean(device))
  const remaining = devices.filter((device) => !prioritizedDeviceIds.includes(device.id))
  return [...prioritized, ...remaining]
}

// 摘要区优先命中当前连接设备 id，旧快照缺失时再回退到任意已连接设备。
export const selectActiveDevice = (
  devices: DeviceViewModel[],
  connection: ConnectionState,
) =>
  devices.find(
    (device) => device.id === connection.currentDeviceId && device.isConnected,
  ) ?? devices.find((device) => device.isConnected)

export const selectOrderedDevices = (state: AppState) =>
  reorderDevicesByPriority(state.devices, state.prioritizedDeviceIds)

export const selectAudioDevices = (state: AppState) =>
  selectOrderedDevices(state).filter((device) => device.supportsAudio)

export const selectVisibleDevices = (state: AppState) =>
  selectOrderedDevices(state).filter(
    (device) => device.isConnected || device.supportsAudio,
  )

export const selectA2dpAvailability = (state: AppState): A2dpSourceAvailability => {
  if (state.runtime.bridgeMode === 'unavailable') {
    return 'unavailable'
  }
  if (selectAudioDevices(state).length === 0) {
    return 'no-source'
  }
  return 'available'
}

export const selectCockpitCandidate = (state: AppState) => {
  const activeDevice = selectActiveDevice(state.devices, state.connection)
  if (activeDevice) {
    return activeDevice
  }
  return selectAudioDevices(state)[0]
}
