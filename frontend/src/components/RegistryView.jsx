import { useEffect, useState } from 'react'
import { formatDate } from '../lib/format'
import { formatCatalogue, nameScale, splitNames } from '../lib/names'

const BASE_SECTIONS = [
  ['dedication', 'Dedication'],
  ['star', 'Star details'],
  ['certificate', 'Certificate'],
]
const DOCUMENT_SECTION = ['registry-document', 'Registry']

function Detail({ label, value, tone = 'text' }) {
  return (
    <div className="detail">
      <dt>{label}</dt>
      <dd className={`detail-${tone}`}>{value || <span className="muted">Not available</span>}</dd>
    </div>
  )
}

/** "For" + one name, or a couple stacked with a quiet "and" between them. Plain text order is preserved for screen readers. */
function RegistryTitle({ dedicatedTo }) {
  const names = splitNames(dedicatedTo)
  return (
    <h1 className="reg-title" data-scale={nameScale(names)}>
      <span className="reg-for">For</span>{' '}
      <span className="reg-names">
        {names.map((name, i) => (
          <span key={`${name}-${i}`} className="reg-name-group">
            {i > 0 && <><span className="reg-and">and</span>{' '}</>}
            <span className="reg-name">{name}</span>{' '}
          </span>
        ))}
      </span>
    </h1>
  )
}

/** Highlights the section currently in view in the in-page navigation. */
function useActiveSection(idList) {
  const ids = idList.split(',')
  const [active, setActive] = useState(ids[0])
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined
    const visible = new Map()
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((e) => visible.set(e.target.id, e.intersectionRatio))
      const best = [...visible.entries()].sort((a, b) => b[1] - a[1])[0]
      if (best && best[1] > 0) setActive(best[0])
    }, { rootMargin: '-25% 0px -45% 0px', threshold: [0, 0.25, 0.5, 0.75, 1] })
    ids.forEach((id) => { const el = document.getElementById(id); if (el) observer.observe(el) })
    return () => observer.disconnect()
  }, [idList]) // eslint-disable-line react-hooks/exhaustive-deps
  return active
}


/**
 * The customer-facing registry. Shared by the public registry page and the admin preview.
 * certificateUrls / documentUrls: { view, download } for the current context.
 */
export default function RegistryView({ registry, certificateUrls, documentUrls }) {
  const { star = {}, certificate = {}, registry_document: doc = {} } = registry
  const isImage = certificate.content_type?.startsWith('image/')
  const showDocument = Boolean(doc.available && documentUrls)
  // The Registry tab only exists when a registry document has been uploaded.
  const sections = showDocument ? [...BASE_SECTIONS, DOCUMENT_SECTION] : BASE_SECTIONS
  const active = useActiveSection(sections.map(([id]) => id).join(','))

  return (
    <article className="registry">
      <header className="registry-hero">
        <p className="eyebrow">Star registry</p>
        <RegistryTitle dedicatedTo={registry.dedicated_to} />
        <p className="registry-sub">A star dedicated with love</p>
        {registry.dedicated_by && (
          <p className="reg-by">Dedicated by <span>{registry.dedicated_by}</span></p>
        )}
        <nav className="registry-nav" aria-label="Registry sections">
          {sections.map(([id, label]) => (
            <a key={id} href={`#${id}`} aria-current={active === id ? 'true' : undefined}>{label}</a>
          ))}
        </nav>
      </header>

      <section id="dedication" className="registry-section" aria-labelledby="h-dedication">
        <h2 id="h-dedication">Dedication details</h2>
        <dl className="details">
          <Detail label="Dedicated to" value={registry.dedicated_to} tone="name" />
          <Detail label="Dedicated by" value={registry.dedicated_by} tone="name" />
          <Detail label="Date of dedication" value={formatDate(registry.dedication_date)} tone="name" />
          <Detail label="Occasion" value={registry.occasion} tone="name" />
        </dl>
        {registry.dedication_message && (
          <figure className="message">
            <blockquote>{registry.dedication_message}</blockquote>
          </figure>
        )}
      </section>

      <section id="star" className="registry-section" aria-labelledby="h-star">
        <h2 id="h-star">Star details</h2>
        <dl className="details">
          <Detail label="Registry number" value={registry.registry_number} tone="ref" />
          <Detail label="Registry code" value={registry.registry_code} tone="ref" />
          <Detail label="Star catalogue" value={formatCatalogue(star.catalogue)} tone="ref" />
          <Detail label="Constellation" value={star.constellation} tone="name" />
          <Detail label="Distance" value={star.distance} tone="name" />
        </dl>
      </section>

      <section id="certificate" className="registry-section" aria-labelledby="h-cert">
        <h2 id="h-cert">Certificate</h2>
        {certificate.available && certificateUrls ? (
          <div className="certificate">
            <div className="cert-preview">
              {isImage ? (
                <img src={certificateUrls.view} alt={`Certificate for ${registry.dedicated_to}`} loading="lazy" />
              ) : (
                <div className="cert-placeholder" aria-hidden="true">
                  <svg viewBox="0 0 64 64" width="44" height="44"><path d="M32 6l6 18 18 8-18 8-6 18-6-18-18-8 18-8z" fill="currentColor" /></svg>
                  <span>Certificate of dedication</span>
                  <small>{registry.registry_number}</small>
                </div>
              )}
            </div>
            <div className="actions">
              <a className="btn btn-primary" href={certificateUrls.view} target="_blank" rel="noopener noreferrer">
                View Certificate<span className="sr-only"> (opens in a new tab)</span>
              </a>
              <a className="btn btn-ghost" href={certificateUrls.download}>Download Certificate</a>
            </div>
          </div>
        ) : (
          <p className="muted unavailable">Certificate currently unavailable.</p>
        )}
      </section>

      {showDocument && (
        <section id="registry-document" className="registry-section" aria-labelledby="h-registry-doc">
          <h2 id="h-registry-doc">Registry document</h2>
          <p className="doc-lede">Your registry, kept as a document you can keep and share.</p>
          <div className="actions center">
            <a className="btn btn-primary" href={documentUrls.view} target="_blank" rel="noopener noreferrer">
              View Registry<span className="sr-only"> (opens in a new tab)</span>
            </a>
            <a className="btn btn-ghost" href={documentUrls.download}>Download Registry</a>
          </div>
        </section>
      )}
    </article>
  )
}
