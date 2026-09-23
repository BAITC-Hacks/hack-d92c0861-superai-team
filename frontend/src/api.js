// Owner: Sayat. All HTTP paths live here. No LLM secrets in the browser.
let token = ''
export function setToken(value) { token = value.trim() }
export class ApiError extends Error {
  constructor(status, message, detail) { super(message); this.status = status; this.detail = detail }
}
async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const headers = new Headers(options.headers || {})
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`/api${path}`, { ...options, headers, signal: controller.signal })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new ApiError(response.status,
        body.detail?.message || (typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`),
        body.detail)
    }
    return body
  } catch (error) {
    if (error.name === 'AbortError') throw new ApiError(408, 'Превышено время ожидания', null)
    throw error
  } finally { clearTimeout(timer) }
}
export const api = {
  health: () => request('/health'),
  me: () => request('/auth/me'),
  employees: () => request('/employees'),
  profile: id => request(`/employees/${encodeURIComponent(id)}`),
  recommendations: id => request(`/employees/${encodeURIComponent(id)}/recommendations`),
  events: () => request('/events'),
  skills: () => request('/skills'),
  complete: (id, payload) => request(`/employees/${encodeURIComponent(id)}/complete`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload),
  }),
  hrOverview: () => request('/hr/overview'),
  importFiles: (employees, history) => {
    const body = new FormData()
    if (employees) body.append('employees', employees)
    if (history) body.append('history', history)
    return request('/admin/import', {method:'POST', body})
  },
}
