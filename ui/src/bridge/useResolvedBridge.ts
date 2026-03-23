import { useEffect, useState } from 'react'

import { resolveBridge } from './index'
import type { BackendBridge } from './types'

export function useResolvedBridge(bridge?: BackendBridge): BackendBridge {
  const [resolvedBridge, setResolvedBridge] = useState<BackendBridge>(() =>
    bridge ?? resolveBridge(),
  )

  useEffect(() => {
    if (bridge) {
      setResolvedBridge(bridge)
      return
    }

    const refreshBridge = () => {
      setResolvedBridge(resolveBridge())
    }

    refreshBridge()
    window.addEventListener('pywebviewready', refreshBridge)

    return () => {
      window.removeEventListener('pywebviewready', refreshBridge)
    }
  }, [bridge])

  return bridge ?? resolvedBridge
}
