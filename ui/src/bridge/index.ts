import { createMockBridge } from './mockBridge'
import type { BackendBridge } from './types'

declare global {
  interface Window {
    audioblueBridge?: BackendBridge
  }
}

export const resolveBridge = (): BackendBridge => window.audioblueBridge ?? createMockBridge()

export * from './types'
