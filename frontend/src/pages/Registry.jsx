import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import RecoveryEmailPrompt from '../components/RecoveryEmailPrompt'
import RegistryView from '../components/RegistryView'
import { VerifyLink } from '../components/VerifyModal'
import { InstagramLink } from '../components/Ui'
import { api } from '../lib/api'
import { useMeta } from '../lib/meta'

/** Remembers a skip for this browser tab only, so the offer returns the next time the customer verifies. */
const promptKey = (id) => `ofs-email-prompt-${id}`
function promptSkipped(id) {
  try { return sessionStorage.getItem(promptKey(id)) === '1' } catch { return false }
}

export default function Registry() {
  const { publicId } = useParams()
  const [state, setState] = useState({ status: 'loading' })
  const [promptOpen, setPromptOpen] = useState(false)
  useMeta({ title: 'Your Star Registry', noindex: true })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    api.registry(publicId)
      .then((data) => {
        if (cancelled) return
        setState({ status: 'ready', data })
        // Offered only when no recovery email is saved yet, and not again after a skip in this tab.
        setPromptOpen(data.has_contact_email === false && !promptSkipped(publicId))
      })
      .catch((err) => !cancelled && setState({ status: 'error', err }))
    return () => { cancelled = true }
  }, [publicId])

  if (state.status === 'loading') {
    return <p className="status-line" role="status">Opening your registry…</p>
  }
  if (state.status === 'error') {
    const { err } = state
    if (err.status === 401) return <Navigate to="/verify" state={{ expired: true }} replace />
    const notFound = err.status === 404
    return (
      <section className="verify">
        <div className="container verify-wrap">
          <div className="card result-card" role="alert">
            <h1 className="h2">{notFound ? 'Registry Not Found' : 'Something went wrong'}</h1>
            <p>{notFound ? 'This registry is not available. Please verify your registry details again.' : err.message}</p>
            <div className="actions center">
              <VerifyLink className="btn btn-primary">Verify Registry</VerifyLink>
              <InstagramLink className="btn btn-ghost">Contact Support</InstagramLink>
            </div>
          </div>
        </div>
      </section>
    )
  }

  return (
    <div className="container registry-wrap">
      <RegistryView
        registry={state.data}
        documentUrls={{
          certificate: { view: api.certificateUrl(publicId), download: api.certificateUrl(publicId, true) },
          registry_document: { view: api.registryDocumentUrl(publicId), download: api.registryDocumentUrl(publicId, true) },
        }}
      />
      {promptOpen && (
        <RecoveryEmailPrompt
          publicId={publicId}
          onClose={() => {
            setPromptOpen(false)
            try { sessionStorage.setItem(promptKey(publicId), '1') } catch { /* private mode: it may simply ask again */ }
          }}
          onSaved={() => setState((s) => ({ ...s, data: { ...s.data, has_contact_email: true } }))}
        />
      )}
      <p className="registry-footer">
        <VerifyLink className="text-link">Verify another registry</VerifyLink>
      </p>
    </div>
  )
}
