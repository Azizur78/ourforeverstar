// Injected at build time from INSTAGRAM_URL in the project-root .env (see vite.config.js).
/* global __INSTAGRAM_URL__ */
export const INSTAGRAM_URL = typeof __INSTAGRAM_URL__ === 'string' ? __INSTAGRAM_URL__ : ''
// Customer-facing brand presentation. Technical identifiers (repo, routes, env, API) stay `ourforeverstar`.
export const SITE_NAME = 'Our Forever Star'
