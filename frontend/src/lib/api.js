/**
 * Thin fetch wrapper around the FastAPI backend (services/api).
 *
 * Base URL comes from VITE_API_BASE_URL (see .env.example) so the same
 * build can point at localhost in dev and a real host in prod without
 * a code change - standard Vite env-var convention (only import.meta.env.VITE_*
 * vars are exposed to client code, everything else is stripped at build time).
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const TOKEN_KEY = 'wanderplan_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const isJson = res.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await res.json().catch(() => null) : null

  if (!res.ok) {
    // FastAPI's HTTPException shape is {"detail": "..."} - that's the
    // human-readable message worth surfacing in the UI.
    const message = data?.detail || res.statusText || 'Something went wrong'
    throw new ApiError(message, res.status)
  }

  return data
}

export const authApi = {
  signup: (email, password) => request('/api/auth/signup', { method: 'POST', body: { email, password } }),
  login: (email, password) => request('/api/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request('/api/auth/me', { auth: true }),
}

export const tripsApi = {
  plan: (query) => request('/api/trips/plan', { method: 'POST', body: { query }, auth: true }),
  list: () => request('/api/trips', { auth: true }),
  get: (tripId) => request(`/api/trips/${tripId}`, { auth: true }),
}
