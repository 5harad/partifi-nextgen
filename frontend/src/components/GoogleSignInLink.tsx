import { useGoogleLogin } from '@react-oauth/google'
import type { CSSProperties, ReactNode } from 'react'

type Props = {
  onLogin: (code: string, redirectUri: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

/**
 * Custom-styled sign-in link using GIS auth-code flow (popup).
 * Backend exchanges the code for an ID token — no GIS iframe in the page.
 */
export function GoogleSignInLink({
  onLogin,
  children = 'Sign In',
  className,
  style,
}: Props) {
  const login = useGoogleLogin({
    flow: 'auth-code',
    scope: 'openid profile email',
    onSuccess: (response) => {
      void onLogin(response.code, window.location.origin).catch((err: unknown) => {
        window.alert(err instanceof Error ? err.message : 'Login failed')
      })
    },
    onError: () => window.alert('Google sign in failed'),
  })

  return (
    <a
      href="#"
      className={className}
      style={style}
      onClick={(e) => {
        e.preventDefault()
        login()
      }}
    >
      {children}
    </a>
  )
}
