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

export function Disclaimer() {
  return (
    <p className="disclaimer">
      ourforeverstar is a celestial dedication and gifting experience. A dedication is a symbolic gift recorded in the
      ourforeverstar registry; it does not confer legal or physical ownership of any star or celestial body.
    </p>
  )
}
