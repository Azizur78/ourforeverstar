import { Link } from 'react-router-dom'
import { INSTAGRAM_URL } from '../lib/config'

/** Opens the official Instagram profile (or falls back to the Contact page if not configured). */
export function InstagramLink({ children, className = 'btn btn-primary' }) {
  if (!INSTAGRAM_URL) {
    return <Link to="/contact" className={className}>{children}</Link>
  }
  return (
    <a href={INSTAGRAM_URL} className={className} target="_blank" rel="noopener noreferrer">
      {children}<span className="sr-only"> (opens Instagram in a new tab)</span>
    </a>
  )
}

export function PageHero({ eyebrow, title, children }) {
  return (
    <header className="page-hero">
      <div className="container narrow">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {children && <p className="lede">{children}</p>}
      </div>
    </header>
  )
}

export function Section({ title, eyebrow, children, narrow = false, className = '' }) {
  return (
    <section className={`section ${className}`}>
      <div className={`container ${narrow ? 'narrow' : ''}`}>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        {title && <h2>{title}</h2>}
        {children}
      </div>
    </section>
  )
}

export function CtaBand({ title, children, actions }) {
  return (
    <section className="section">
      <div className="container">
        <div className="cta-band">
          <h2>{title}</h2>
          <p>{children}</p>
          <div className="actions center">{actions}</div>
        </div>
      </div>
    </section>
  )
}

const NOT_RECOGNISED_BY = ['NASA', 'IAU', 'Governments']

/** Plain-spoken transparency panel: what a dedication is recognised by, and what it is not. */
export function RecognitionPanel() {
  return (
    <section className="section" aria-labelledby="recognition-title">
      <div className="container">
        <div className="recognition">
          <p className="eyebrow">Universal recognition</p>
          <h2 id="recognition-title">Honest about what a dedication is</h2>
          <p className="recognition-lead">
            Your dedication is recognised <em>within our registry only.</em>
          </p>
          <p className="recognition-not" id="recognition-not">It is not recognised by</p>
          <ul className="recognition-list" aria-labelledby="recognition-not">
            {NOT_RECOGNISED_BY.map((name) => <li key={name}>{name}</li>)}
          </ul>
          <p className="recognition-note">
            It is a personal, symbolic keepsake, offered with complete transparency, so that what you give is exactly what it appears to be.
          </p>
        </div>
      </div>
    </section>
  )
}

/** Why orders happen on Instagram: the relationship with each customer. */
export function RelationshipPanel() {
  return (
    <section className="section" aria-labelledby="relationship-title">
      <div className="container narrow">
        <div className="relationship">
          <svg className="relationship-heart" viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
            <path d="M12 21C12 21 3 15.5 3 9.5 3 6.5 5.2 4.5 7.6 4.5c1.8 0 3.4 1 4.4 2.6 1-1.6 2.6-2.6 4.4-2.6 2.4 0 4.6 2 4.6 5C21 15.5 12 21 12 21z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          <h2 id="relationship-title">Every order begins with a conversation</h2>
          <p>
            We take orders on Instagram because we want to build a relationship with every person who places one.
          </p>
          <p className="relationship-quote">
            Every member of the Our Forever Star family is important to us.
          </p>
          <div className="actions center">
            <InstagramLink>Message us on Instagram</InstagramLink>
          </div>
        </div>
      </div>
    </section>
  )
}

export function Disclaimer() {
  return (
    <p className="disclaimer">
      Our Forever Star is a celestial dedication and gifting experience. A dedication is a symbolic gift recorded in the
      Our Forever Star registry; it does not confer legal or physical ownership of any star or celestial body.
    </p>
  )
}
