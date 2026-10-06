import { useEffect } from 'react'
import { SITE_NAME } from './config'

function setMeta(attr, key, content) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

/** Per-page title, description, Open Graph tags and optional noindex. */
export function useMeta({ title, description, noindex = false }) {
  useEffect(() => {
    const full = title ? `${title} | ${SITE_NAME}` : `${SITE_NAME} | Dedicate a Star to Someone You Love`
    document.title = full
    if (description) {
      setMeta('name', 'description', description)
      setMeta('property', 'og:description', description)
    }
    setMeta('property', 'og:title', full)
    setMeta('property', 'og:url', window.location.href)
    setMeta('name', 'robots', noindex ? 'noindex, nofollow' : 'index, follow')
  }, [title, description, noindex])
}
