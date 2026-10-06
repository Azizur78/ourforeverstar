import { formatDate } from '../lib/format'

function Detail({ label, value }) {
  return (
    <div className="detail">
      <dt>{label}</dt>
      <dd>{value || <span className="muted">Not available</span>}</dd>
    </div>
  )
}

/**
 * The customer-facing registry. Shared by the public registry page and the admin preview.
 * certificateUrls: { view, download } for the current context.
 */
export default function RegistryView({ registry, certificateUrls }) {
  const { star = {}, certificate = {} } = registry
  const isImage = certificate.content_type?.startsWith('image/')

  return (
    <article className="registry">
      <header className="registry-hero">
        <p className="eyebrow">Star registry</p>
        <h1>For {registry.dedicated_to} and {registry.dedicated_by}</h1>
        <p className="registry-sub">A star dedicated with love</p>
        <nav className="registry-nav" aria-label="Registry sections">
          <a href="#dedication">Dedication</a>
          <a href="#star">Star details</a>
          <a href="#certificate">Certificate</a>
        </nav>
      </header>

      <section id="dedication" className="registry-section" aria-labelledby="h-dedication">
        <h2 id="h-dedication">Dedication details</h2>
        <dl className="details">
          <Detail label="Dedicated to" value={registry.dedicated_to} />
          <Detail label="Dedicated by" value={registry.dedicated_by} />
          <Detail label="Date of dedication" value={formatDate(registry.dedication_date)} />
          <Detail label="Occasion" value={registry.occasion} />
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
          <Detail label="Registry number" value={registry.registry_number} />
          <Detail label="Registry code" value={registry.registry_code} />
          <Detail label="Star catalogue" value={star.catalogue} />
          <Detail label="Constellation" value={star.constellation} />
          <Detail label="Distance" value={star.distance} />
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
    </article>
  )
}
