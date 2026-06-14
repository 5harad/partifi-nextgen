import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

type Props = {
  onLogin: (idToken: string) => Promise<void>
  children?: ReactNode
  className?: string
  style?: CSSProperties
}

/** GIS iframe minimum; clipped to the link box in the portaled overlay. */
const GOOGLE_BUTTON_WIDTH = 120

export function GoogleSignInLink({
  onLogin,
  children = 'Sign In',
  className,
  style,
}: Props) {
  const anchorRef = useRef<HTMLAnchorElement>(null)
  const [overlayStyle, setOverlayStyle] = useState<CSSProperties>({ display: 'none' })

  const syncOverlay = useCallback(() => {
    const anchor = anchorRef.current
    if (!anchor) return
    const rect = anchor.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) {
      setOverlayStyle({ display: 'none' })
      return
    }
    setOverlayStyle({
      position: 'fixed',
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: Math.max(rect.height, 40),
      opacity: 0,
      overflow: 'hidden',
      zIndex: 10000,
      cursor: 'pointer',
    })
  }, [])

  useLayoutEffect(() => {
    syncOverlay()
    const anchor = anchorRef.current
    if (!anchor) return undefined

    const observer = new ResizeObserver(syncOverlay)
    observer.observe(anchor)
    window.addEventListener('resize', syncOverlay)
    window.addEventListener('scroll', syncOverlay, true)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', syncOverlay)
      window.removeEventListener('scroll', syncOverlay, true)
    }
  }, [syncOverlay, children])

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
        ref={anchorRef}
        href="#"
        className={className}
        style={style}
        onClick={(e) => e.preventDefault()}
      >
        {children}
      </a>
      {createPortal(
        <div aria-label="Sign in with Google" style={overlayStyle}>
          <GoogleLogin
            onSuccess={handleSuccess}
            onError={() => window.alert('Google sign in failed')}
            useOneTap={false}
            type="standard"
            size="medium"
            text="signin_with"
            width={GOOGLE_BUTTON_WIDTH}
          />
        </div>,
        document.body,
      )}
    </>
  )
}
