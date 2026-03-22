import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'
import { createMockBridge } from './bridge/mockBridge'

afterEach(() => {
  window.location.hash = ''
})

describe('AudioBlue Control Center integration', () => {
  it('renders shell navigation and overview by default', async () => {
    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByRole('button', { name: 'Overview' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Devices' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Automation' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeVisible()
    expect(await screen.findByText('Connection Overview')).toBeVisible()
  })

  it('binds rule toggles to state changes', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Automation' }))

    const toggle = await screen.findByRole('checkbox', {
      name: 'Auto-connect when this device appears',
    })

    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    expect(toggle).toBeChecked()
  })

  it('switches theme mode from settings', async () => {
    render(<App bridge={createMockBridge()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Settings' }))
    await userEvent.selectOptions(
      await screen.findByLabelText('Theme mode'),
      'dark',
    )

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    })
  })

  it('renders the compact quick panel surface for tray entrypoint', async () => {
    window.location.hash = '#quick-panel'

    render(<App bridge={createMockBridge()} />)

    expect(await screen.findByLabelText('Tray quick panel')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Overview' })).not.toBeInTheDocument()
  })
})
