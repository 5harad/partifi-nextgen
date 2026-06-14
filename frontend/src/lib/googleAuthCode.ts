type CodeResponse = {
  code?: string
  error?: string
}

type CodeClient = {
  requestCode: () => void
}

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initCodeClient: (config: {
            client_id: string
            scope: string
            ux_mode?: 'popup' | 'redirect'
            callback: (response: CodeResponse) => void
          }) => CodeClient
        }
      }
    }
  }
}

let codeClient: CodeClient | null = null
let onSuccessRef: ((code: string) => void) | null = null
let onErrorRef: (() => void) | null = null

/** Lazy, singleton GIS auth-code client — init on first click only (no page-load iframe). */
export function requestGoogleAuthCode(
  clientId: string,
  onSuccess: (code: string) => void,
  onError: () => void,
): void {
  const oauth2 = window.google?.accounts?.oauth2
  if (!oauth2) {
    onError()
    return
  }

  onSuccessRef = onSuccess
  onErrorRef = onError

  if (!codeClient) {
    codeClient = oauth2.initCodeClient({
      client_id: clientId,
      scope: 'openid profile email',
      ux_mode: 'popup',
      callback: (response) => {
        if (response.code) {
          onSuccessRef?.(response.code)
          return
        }
        onErrorRef?.()
      },
    })
  }

  codeClient.requestCode()
}
