import { useCallback, useSyncExternalStore } from 'react'

import { resolveBridge } from './index'
import type { BackendBridge } from './types'

// 负责绑定 pywebview ready 事件并返回已经初始化的桥接实例。
export function useResolvedBridge(bridge?: BackendBridge): BackendBridge {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      // 显式传入桥接实例时，不再监听宿主就绪事件，避免重复刷新。
      if (bridge) {
        return () => undefined
      }

      // 等待 pywebview 宿主准备好后，再重新解析默认桥接实例。
      window.addEventListener('pywebviewready', onStoreChange)
      return () => {
        window.removeEventListener('pywebviewready', onStoreChange)
      }
    },
    [bridge],
  )

  // `getSnapshot` 优先返回显式桥接，否则退回到全局解析出的默认桥接。
  const getSnapshot = useCallback(() => bridge ?? resolveBridge(), [bridge])

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
