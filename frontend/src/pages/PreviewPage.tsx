import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PreviewEditor } from '../components/preview/PreviewEditor'

export function PreviewPage() {
  const { privateId } = useParams<{ privateId: string }>()

  if (!privateId) return null

  return (
    <Layout>
      <div className="site-canvas site-canvas--long-pole site-canvas--preview">
        <div className="stand-stage">
          <PreviewEditor privateId={privateId} />
        </div>
        <div className="site-canvas-seam" aria-hidden="true" />
        <div className="site-canvas-fill" aria-hidden="true" />
      </div>
    </Layout>
  )
}
