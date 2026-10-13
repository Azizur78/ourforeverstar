import { useEffect, useMemo, useState } from 'react'
import { formatDate } from '../lib/format'
import { savingHint } from '../lib/platform'
import { formatCatalogue, nameScale, splitNames } from '../lib/names'

const SECTIONS = [
  ['dedication', 'Dedication'],
  ['star', 'Star details'],
  ['documents', 'Documents'],
]
// The two customer PDFs, in the order they are shown.
const DOCUMENTS = [
  ['certificate', 'Star Dedication Certificate'],
  ['registry_document', 'Certificate of Celestial Registry'],
]

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
 * One document. View is the main action; saving a copy is a small, quiet option.
 * A document that is not uploaded yet gets a plain explanation instead.
 */
function DocumentCard({ label, info = {}, urls }) {
  const id = `doc-${label.toLowerCase().replace(/[^a-z]+/g, '-')}`
  const saveHint = useMemo(savingHint, [])

  return (
    <article className="doc-card" aria-labelledby={id}>
      <h3 id={id}>{label}</h3>
      {info.available && urls ? (
        <>
          <div className="actions center">
            <a className="btn btn-primary" href={urls.view} target="_blank" rel="noopener noreferrer">
              View<span className="sr-only"> {label} (opens in a new tab)</span>
            </a>
          </div>
          {saveHint && <p className="hint doc-save-hint">{saveHint}</p>}
          <a className="doc-download" href={urls.download}>
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Download<span className="sr-only"> {label} (PDF)</span>
          </a>
        </>
      ) : (
        <p className="muted doc-missing" role="status">Not uploaded yet. It will appear here as soon as it is ready.</p>
      )}
    </article>
  )
}

/**
 * The customer-facing registry. Shared by the public registry page and the admin preview.
 * documentUrls: { certificate: {view, download}, registry_document: {view, download} } for the current context.
 */
export default function RegistryView({ registry, documentUrls = {} }) {
  const { star = {} } = registry
  const active = useActiveSection(SECTIONS.map(([id]) => id).join(','))

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
          {SECTIONS.map(([id, label]) => (
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

      <section id="documents" className="registry-section" aria-labelledby="h-docs">
        <h2 id="h-docs">Your Documents</h2>
        <p className="doc-lede">View your documents here. A small Download option sits under each one if you would like a copy.</p>
        <div className="doc-grid">
          {DOCUMENTS.map(([key, label]) => (
            <DocumentCard key={key} label={label} info={registry[key]} urls={documentUrls[key]} />
          ))}
        </div>
      </section>
    </article>
  )
}
