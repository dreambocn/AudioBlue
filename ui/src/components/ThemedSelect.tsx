import type { ReactNode, SelectHTMLAttributes } from 'react'

interface ThemedSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  children: ReactNode
}

export function ThemedSelect({
  children,
  className = '',
  ...props
}: ThemedSelectProps) {
  const selectClassName = className ? `themed-select ${className}` : 'themed-select'

  return (
    <span className="themed-select-shell">
      <select {...props} className={selectClassName}>
        {children}
      </select>
      <span
        className="themed-select-indicator"
        data-testid="themed-select-indicator"
        aria-hidden="true"
      >
        <span className="themed-select-indicator-line" />
        <span className="themed-select-indicator-line" />
      </span>
    </span>
  )
}
