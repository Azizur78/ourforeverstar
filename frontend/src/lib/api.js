export class ApiError extends Error {
  constructor(status, message, extra = {}) {
    super(message)
    this.status = status
    this.fieldErrors = extra.errors || []
    this.field = extra.field || null
    this.retryAfter = extra.retryAfter || null
    this.network = status === 0
  }
}

async function request(path, { method = 'GET', json, body } = {}) {
  const init = { method, credentials: 'same-origin', headers: {} }
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(json)
  } else if (body) {
    init.body = body
  }
  let res
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'We could not reach the server. Please check your connection and try again.')
  }
  let data = null
  try {
    data = await res.json()
  } catch {
    /* non-JSON or empty body */
  }
  if (!res.ok) {
    const message = data?.message || (res.status >= 500 ? 'Something went wrong. Please try again.' : 'Request failed.')
    throw new ApiError(res.status, message, { ...data, retryAfter: res.headers.get('Retry-After') })
  }
  return data
}

const qs = (params) => {
  const s = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => v !== '' && v != null && s.set(k, v))
  const out = s.toString()
  return out ? `?${out}` : ''
}

export const api = {
  verify: (registry_number, registry_code) =>
    request('/api/registries/verify', { method: 'POST', json: { registry_number, registry_code } }),
  registry: (publicId) => request(`/api/registries/${encodeURIComponent(publicId)}`),
  certificateUrl: (publicId, download = false) =>
    `/api/registries/${encodeURIComponent(publicId)}/certificate${download ? '?download=1' : ''}`,
  registryDocumentUrl: (publicId, download = false) =>
    `/api/registries/${encodeURIComponent(publicId)}/registry-document${download ? '?download=1' : ''}`,

  admin: {
    login: (username, password) => request('/api/admin/login', { method: 'POST', json: { username, password } }),
    logout: () => request('/api/admin/logout', { method: 'POST' }),
    changePassword: (current_password, new_password, confirm_new_password) =>
      request('/api/admin/change-password', {
        method: 'POST', json: { current_password, new_password, confirm_new_password },
      }),
    me: () => request('/api/admin/me'),
    stats: () => request('/api/admin/stats'),
    list: (params) => request(`/api/admin/registries${qs(params)}`),
    get: (id) => request(`/api/admin/registries/${id}`),
    // One request creates every record (with its optional certificate and registry document) or none.
    // certificates / registryDocuments: [{index, file}]
    createBatch: (records, certificates = [], registryDocuments = []) => {
      const form = new FormData()
      form.append('records', JSON.stringify(records))
      form.append('certificate_indexes', JSON.stringify(certificates.map((c) => c.index)))
      certificates.forEach((c) => form.append('certificates', c.file))
      form.append('registry_document_indexes', JSON.stringify(registryDocuments.map((c) => c.index)))
      registryDocuments.forEach((c) => form.append('registry_documents', c.file))
      return request('/api/admin/registries/batch', { method: 'POST', body: form })
    },
    update: (id, data) => request(`/api/admin/registries/${id}`, { method: 'PUT', json: data }),
    setStatus: (id, status) => request(`/api/admin/registries/${id}/status`, { method: 'PATCH', json: { status } }),
    uploadCertificate: (id, file) => {
      const form = new FormData()
      form.append('file', file)
      return request(`/api/admin/registries/${id}/certificate`, { method: 'POST', body: form })
    },
    uploadRegistryDocument: (id, file) => {
      const form = new FormData()
      form.append('file', file)
      return request(`/api/admin/registries/${id}/registry-document`, { method: 'POST', body: form })
    },
    registryDocumentUrl: (id, download = false) =>
      `/api/admin/registries/${id}/registry-document${download ? '?download=1' : ''}`,
    certificateUrl: (id, download = false) =>
      `/api/admin/registries/${id}/certificate${download ? '?download=1' : ''}`,
  },
}
