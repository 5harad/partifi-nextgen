import type { ReactNode } from 'react'
import { Footer } from './Footer'
import { Header } from './Header'

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="site-layout">
      <Header />
      <div className="site-main">{children}</div>
      <Footer />
    </div>
  )
}
