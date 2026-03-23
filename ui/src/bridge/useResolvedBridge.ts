import { useCallback, useSyncExternalStore } from 'react'

import { resolveBridge } from './index'
import type { BackendBridge } from './types'

export function useResolvedBridge(bridge?: BackendBridge): BackendBridge {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      if (bridge) {
        return () => undefined
      }

      window.addEventListener('pywebviewready', onStoreChange)
      return () => {
        window.removeEventListener('pywebviewready', onStoreChange)
      }
    },
    [bridge],
  )

  const getSnapshot = useCallback(() => bridge ?? resolveBridge(), [bridge])

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
