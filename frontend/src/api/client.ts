/**
 * Cartographer — Axios API Client
 *
 * Pre-configured axios instance with:
 * - Base URL from env
 * - JWT token injection via interceptor
 * - Token refresh on 401
 * - Structlog-compatible error logging
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@store/authStore'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
})

// ── Request interceptor: inject JWT Bearer token ────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

// ── Response interceptor: handle 401 → token refresh ──────────────────────
let isRefreshing = false
let refreshQueue: Array<(token: string) => void> = []

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const { refreshToken, setTokens, logout } = useAuthStore.getState()
      if (!refreshToken) {
        logout()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue this request until the refresh completes
        return new Promise((resolve) => {
          refreshQueue.push((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(originalRequest))
          })
        })
      }

      isRefreshing = true
      try {
        const response = await axios.post(
          `${import.meta.env.VITE_API_BASE_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        )
        const { access_token, refresh_token } = response.data
        setTokens(access_token, refresh_token)

        // Replay queued requests
        refreshQueue.forEach((cb) => cb(access_token))
        refreshQueue = []

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return apiClient(originalRequest)
      } catch {
        logout()
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// ── SSE helper for streaming endpoints ─────────────────────────────────────
export function createSSEConnection(
  url: string,
  onToken: (token: string) => void,
  onDone: (data: Record<string, unknown>) => void,
  onError: (err: string) => void,
  onAgentState?: (state: string) => void,
  body?: Record<string, unknown>
): EventSource {
  const { accessToken } = useAuthStore.getState()
  const fullUrl = `${import.meta.env.VITE_API_BASE_URL}${url}`

  // Native EventSource doesn't support custom headers — use fetch-based SSE
  const controller = new AbortController()

  fetch(fullUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      Accept: 'text/event-stream',
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  }).then(async (response) => {
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) return

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'token') onToken(data.content)
            else if (data.type === 'done') onDone(data)
            else if (data.type === 'error') onError(data.message)
            else if (data.type === 'agent_trace' && onAgentState) onAgentState(data.content)
          } catch {
            // Non-JSON line, skip
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') onError(String(err))
  })

  // Return a fake EventSource-like object with close()
  return { close: () => controller.abort() } as unknown as EventSource
}
