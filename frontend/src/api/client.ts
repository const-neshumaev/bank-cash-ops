import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import i18n from '../i18n'

const ACCESS_KEY = 'bco.access'
const REFRESH_KEY = 'bco.refresh'

/** Thin wrapper around localStorage that keeps both JWT tokens in sync. */
export const tokenStorage = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh !== undefined) {
      localStorage.setItem(REFRESH_KEY, refresh)
    }
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api: AxiosInstance = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  // Tell the backend which language to render messages and reference data in.
  config.headers['Accept-Language'] = i18n.language
  const token = tokenStorage.access()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

async function requestNewAccessToken(): Promise<string> {
  const refresh = tokenStorage.refresh()
  if (!refresh) {
    throw new Error('No refresh token available')
  }
  // A bare axios call avoids the interceptor recursion.
  const { data } = await axios.post('/api/auth/refresh/', { refresh })
  tokenStorage.set(data.access, data.refresh)
  return data.access as string
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    const status = error.response?.status
    const isAuthEndpoint =
      original?.url?.includes('/auth/login/') || original?.url?.includes('/auth/refresh/')

    if (
      status === 401 &&
      original &&
      !original._retry &&
      !isAuthEndpoint &&
      tokenStorage.refresh()
    ) {
      original._retry = true
      try {
        refreshPromise = refreshPromise ?? requestNewAccessToken()
        const access = await refreshPromise
        refreshPromise = null
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      } catch (refreshError) {
        refreshPromise = null
        tokenStorage.clear()
        window.dispatchEvent(new Event('bco:logout'))
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  },
)
