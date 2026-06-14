import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { type CSSProperties, type ReactNode } from 'react'

type Props = {
  onLogin: (idToken: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

/** Pixel width for the invisible Google button overlay (must cover the visible label). */
const OVERLAY_WIDTH = 160

export function GoogleSignInLink({
  onLogin,
  children = 'Sign In',
  className,
  style,
}: Props) {
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
    <span
      className={className}
      style={{
        position: 'relative',
        display: 'inline-block',
        verticalAlign: 'baseline',
        minWidth: OVERLAY_WIDTH,
        minHeight: 40,
        ...style,
      }}
    >
      <span aria-hidden="true" style={{ pointerEvents: 'none' }}>
        {children}
      </span>
      <span
        aria-label="Sign in with Google"
        style={{
          position: 'absolute',
          inset: 0,
          opacity: 0,
          overflow: 'hidden',
          cursor: 'pointer',
        }}
      >
        <GoogleLogin
          onSuccess={handleSuccess}
          onError={() => window.alert('Google sign in failed')}
          useOneTap={false}
          type="standard"
          size="medium"
          text="signin_with"
          width={OVERLAY_WIDTH}
        />
      </span>
    </span>
  )
}
