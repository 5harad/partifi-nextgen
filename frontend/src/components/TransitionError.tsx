import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

type Props = {
  message: string
  children?: ReactNode
  showReturnHome?: boolean
}

export function TransitionError({
  message,
  children,
  showReturnHome = true,
}: Props) {
  const navigate = useNavigate()

  return (
    <div id="main" style={{ height: '750px' }}>
      <img
        src="/images/notes_bg.jpg"
        width={1190}
        height={252}
        style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
        alt=""
      />
      <div id="transition" className="transition-error">
        <div id="transition-text">{message}</div>
        {(children || showReturnHome) && (
          <div id="transition-actions">
            {children}
            {showReturnHome ? (
              <TransitionErrorButton label="Return to home" onClick={() => navigate('/')} />
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}

type ButtonProps = {
  label: string
  onClick?: () => void
  disabled?: boolean
}

export function TransitionErrorButton({ label, onClick, disabled = false }: ButtonProps) {
  return (
    <div
      className={`copy-button${disabled ? ' is-disabled' : ''}`}
      onClick={disabled ? undefined : onClick}
      onKeyDown={() => {}}
      role="button"
      tabIndex={disabled ? -1 : 0}
    >
      {label}
    </div>
  )
}
