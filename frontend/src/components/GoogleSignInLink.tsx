import { useGoogleLogin } from '@react-oauth/google'
import type { CSSProperties, ReactNode } from 'react'

type Props = {
  onLogin: (accessToken: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

export function GoogleSignInLink({
  onLogin,
  children = 'Sign In',
  className,
  style,
}: Props) {
  const login = useGoogleLogin({
    scope: 'openid profile email',
    onSuccess: (response) => {
      void onLogin(response.access_token).catch((err: unknown) => {
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
