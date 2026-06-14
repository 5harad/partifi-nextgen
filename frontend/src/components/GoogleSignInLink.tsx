import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { type CSSProperties, type ReactNode } from 'react'

type Props = {
  onLogin: (idToken: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

/** GIS button width; overlay is out-of-flow so this does not widen the menu. */
const OVERLAY_WIDTH = 120

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
    <span className={className} style={{ position: 'relative', display: 'inline', ...style }}>
      {children}
      <span
        aria-label="Sign in with Google"
        style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: OVERLAY_WIDTH,
          height: 40,
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
