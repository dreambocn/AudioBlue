import { describe, expect, it } from 'vitest'
import config from './vite.config'

describe('vite desktop asset loading', () => {
  it('uses a relative base path for file-backed desktop hosts', () => {
    expect(config.base).toBe('./')
  })
})
