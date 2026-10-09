import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import logoImage from '../assets/ourforeverstar-logo.jpg'
import { SITE_NAME } from '../lib/config'
import StarField from './StarField'
import { InstagramLink } from './Ui'
import { VerifyLink } from './VerifyModal'

const NAV = [
  ['/', 'Home'],
  ['/celestial-gifting', 'Celestial Gifting'],
  ['/about', 'Our Story'],
  ['/how-it-works', 'How It Works'],
  ['/faq', 'FAQ'],
  ['/contact', 'Contact'],
]

// Footer groups reuse the existing routes; no new pages.
const EXPLORE = NAV.filter(([to]) => ['/', '/celestial-gifting', '/about', '/how-it-works'].includes(to))
const SUPPORT = NAV.filter(([to]) => ['/faq', '/contact'].includes(to))

function Logo() {
  return (
    <Link to="/" className="logo" aria-label={`${SITE_NAME}, home`}>
      <img src={logoImage} alt="" className="logo-mark" width="40" height="40" />
      <span>{SITE_NAME}</span>
    </Link>
  )
}

export default function SiteLayout() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    setOpen(false)
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <StarField />
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="site-header">
        <div className="container header-row">
          <Logo />
          <button className="menu-toggle" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(!open)}>
            <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
            <span className="bars" aria-hidden="true" />
          </button>
          <nav id="site-nav" className={`site-nav ${open ? 'open' : ''}`} aria-label="Main">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
            ))}
            <VerifyLink className="btn btn-ghost btn-sm nav-cta">Verify Registry</VerifyLink>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="container footer-grid">
          <div className="footer-brand">
            <Logo />
            <p className="muted">Some connections are written in the stars.</p>
          </div>
          <nav aria-labelledby="footer-explore">
            <h2 id="footer-explore" className="footer-heading">Explore</h2>
            <ul className="footer-links">
              {EXPLORE.map(([to, label]) => <li key={to}><Link to={to}>{label}</Link></li>)}
            </ul>
          </nav>
          <nav aria-labelledby="footer-support">
            <h2 id="footer-support" className="footer-heading">Support</h2>
            <ul className="footer-links">
              {SUPPORT.map(([to, label]) => <li key={to}><Link to={to}>{label}</Link></li>)}
              <li><VerifyLink>Verify Registry</VerifyLink></li>
            </ul>
          </nav>
          <div className="footer-connect">
            <h2 className="footer-heading">Connect</h2>
            <p className="muted">Orders and enquiries are handled through Instagram.</p>
            <InstagramLink className="btn btn-ghost btn-sm">Message us on Instagram</InstagramLink>
          </div>
        </div>
        <div className="container">
          <p className="legal">
            A star dedication is a symbolic gift recorded in the Our Forever Star registry. It does not confer legal or
            physical ownership of any star or celestial body. &copy; {new Date().getFullYear()} {SITE_NAME}.
          </p>
        </div>
      </footer>
    </>
  )
}
