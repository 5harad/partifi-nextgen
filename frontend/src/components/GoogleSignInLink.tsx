import { useGoogleOAuth } from '@react-oauth/google'
import { useCallback, type CSSProperties, type ReactNode } from 'react'
import { requestGoogleAuthCode } from '../lib/googleAuthCode'

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
  const { clientId, scriptLoadedSuccessfully } = useGoogleOAuth()

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault()
      if (!scriptLoadedSuccessfully) {
        window.alert('Google sign in is not ready yet')
        return
      }
      requestGoogleAuthCode(
        clientId,
        (code) => {
          void onLogin(code, window.location.origin).catch((err: unknown) => {
            window.alert(err instanceof Error ? err.message : 'Login failed')
          })
        },
        () => window.alert('Google sign in failed'),
      )
    },
    [clientId, scriptLoadedSuccessfully, onLogin],
  )

  const classes = ['google-sign-in-link', className].filter(Boolean).join(' ')

  return (
    <a href="#" className={classes || undefined} style={style} onClick={handleClick}>
      {children}
    </a>
  )
}
