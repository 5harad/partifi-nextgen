import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { useRef, type CSSProperties, type ReactNode } from 'react'

type Props = {
  onLogin: (idToken: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

function clickHiddenGoogleButton(container: HTMLDivElement | null) {
  const button = container?.querySelector('[role="button"]')
  if (button instanceof HTMLElement) {
    button.click()
  }
}

export function GoogleSignInLink({
  onLogin,
  children = 'Sign In',
  className,
  style,
}: Props) {
  const googleButtonRef = useRef<HTMLDivElement>(null)

  const handleSuccess = (response: CredentialResponse) => {
    const credential = response.credential
    if (!credential) {
      window.alert('Google sign in failed')
      return
    }
    void onLogin(credential).catch((err: unknown) => {
      window.alert(err instanceof Error ? err.message : 'Login failed')
    })
  }

  return (
    <>
      <a
        href="#"
        className={className}
        style={style}
        onClick={(e) => {
          e.preventDefault()
          clickHiddenGoogleButton(googleButtonRef.current)
        }}
      >
        {children}
      </a>
      <div
        ref={googleButtonRef}
        aria-hidden
        style={{
          position: 'fixed',
          left: -9999,
          width: 1,
          height: 1,
          overflow: 'hidden',
        }}
      >
        <GoogleLogin
          onSuccess={handleSuccess}
          onError={() => window.alert('Google sign in failed')}
          useOneTap={false}
        />
      </div>
    </>
  )
}
