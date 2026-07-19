import type { ReactNode } from 'react'
import { Footer } from './Footer'
import { Header } from './Header'

type Props = {
  children: ReactNode
  showChrome?: boolean
}

export function Layout({ children, showChrome = true }: Props) {
  return (
    <div className="site-layout">
      {showChrome ? <Header /> : null}
      <div className="site-main">{children}</div>
      {showChrome ? <Footer /> : null}
    </div>
  )
}
