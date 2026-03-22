import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LanguageProvider, resolveLanguage, resolveSystemLanguage, useI18n } from './index'

function Probe() {
  const { language, t } = useI18n()
  return (
    <div>
      <span data-testid="lang">{language}</span>
      <span>{t('common.none')}</span>
    </div>
  )
}

describe('i18n', () => {
  it('resolves supported system languages', () => {
    expect(resolveSystemLanguage('zh-HK')).toBe('zh-CN')
    expect(resolveSystemLanguage('zh-CN')).toBe('zh-CN')
    expect(resolveSystemLanguage('en-GB')).toBe('en-US')
  })

  it('resolves preference language', () => {
    expect(resolveLanguage('system', 'zh-HK')).toBe('zh-CN')
    expect(resolveLanguage('system', 'en-US')).toBe('en-US')
    expect(resolveLanguage('en-US', 'zh-CN')).toBe('en-US')
  })

  it('provides translated strings from context', () => {
    render(
      <LanguageProvider preference="zh-CN">
        <Probe />
      </LanguageProvider>,
    )

    expect(screen.getByTestId('lang')).toHaveTextContent('zh-CN')
    expect(screen.getByText('无')).toBeVisible()
  })
})
