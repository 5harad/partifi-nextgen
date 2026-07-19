import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PreviewEditor } from '../components/preview/PreviewEditor'
import { useNoIndex } from '../lib/useNoIndex'

export function PreviewPage() {
  useNoIndex()
  const { privateId } = useParams<{ privateId: string }>()
  const [preparing, setPreparing] = useState(true)
  const handlePreparingChange = useCallback((isPreparing: boolean) => {
    setPreparing(isPreparing)
  }, [])

  if (!privateId) return null

  return (
    <Layout showChrome={!preparing}>
      <div className="site-canvas site-canvas--long-pole site-canvas--preview">
        <div className="stand-stage">
          <PreviewEditor privateId={privateId} onPreparingChange={handlePreparingChange} />
        </div>
        <div className="site-canvas-seam" aria-hidden="true" />
        <div className="site-canvas-fill" aria-hidden="true" />
      </div>
    </Layout>
  )
}
