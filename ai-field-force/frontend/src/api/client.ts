import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
export const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true';

export const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
  withCredentials: true,  // send cookies (refresh_token httpOnly cookie)
});

// ─── Request interceptor ──────────────────────────────────────────────────────

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;

  const lang = localStorage.getItem('lang') ?? 'en';
  config.headers['Accept-Language'] = lang;

  return config;
});

// ─── Refresh-token coordination ───────────────────────────────────────────────
//
// When the access token expires, multiple concurrent API calls all get 401
// simultaneously. We must:
//   1. Have exactly ONE refresh request in flight
//   2. Queue every other 401'd request and replay them with the new token
//   3. If refresh fails, fail every queued request (don't infinite-loop)
//   4. Never try to refresh the refresh call itself

interface QueuedRequest {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}

let isRefreshing = false;
let pendingQueue: QueuedRequest[] = [];

function enqueueRequest(): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    pendingQueue.push({ resolve, reject });
  });
}

function flushQueue(error: unknown, token?: string): void {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else if (token) resolve(token);
  });
  pendingQueue = [];
}

async function attemptRefresh(): Promise<string> {
  // Hit /auth/refresh DIRECTLY using a bare axios instance to bypass our
  // own interceptor (avoids any chance of infinite recursion).
  const res = await axios.post(
    `${BASE_URL}/auth/refresh`,
    {},
    { withCredentials: true },
  );
  const newToken: string | undefined = res.data?.access_token;
  if (!newToken) throw new Error('Refresh response missing access_token');

  localStorage.setItem('access_token', newToken);
  if (res.data?.rep) {
    localStorage.setItem('rep', JSON.stringify(res.data.rep));
  }
  return newToken;
}

function forceLogout(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('rep');
  // Avoid redirect loop if we're already on /login
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

// ─── Response interceptor ─────────────────────────────────────────────────────

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Network error / no response — bail
    if (!error.response || !original) return Promise.reject(error);

    // Only handle 401s
    if (error.response.status !== 401) return Promise.reject(error);

    // Never try to refresh the refresh call itself, or login/logout/register
    const url = original.url ?? '';
    if (
      url.includes('/auth/refresh') ||
      url.includes('/auth/login') ||
      url.includes('/auth/register') ||
      url.includes('/auth/logout') ||
      url.includes('/auth/otp') ||
      url.includes('/auth/google')
    ) {
      return Promise.reject(error);
    }

    // Already retried once — give up
    if (original._retry) {
      forceLogout();
      return Promise.reject(error);
    }
    original._retry = true;

    // Another refresh is in flight — queue and wait
    if (isRefreshing) {
      try {
        const newToken = await enqueueRequest();
        original.headers.Authorization = `Bearer ${newToken}`;
        return client(original);
      } catch (queueErr) {
        return Promise.reject(queueErr);
      }
    }

    // We're the first 401 — drive the refresh
    isRefreshing = true;
    try {
      const newToken = await attemptRefresh();
      flushQueue(null, newToken);
      original.headers.Authorization = `Bearer ${newToken}`;
      return client(original);
    } catch (refreshErr) {
      flushQueue(refreshErr);
      forceLogout();
      return Promise.reject(refreshErr);
    } finally {
      isRefreshing = false;
    }
  },
);

// ─── Helpers (unchanged) ──────────────────────────────────────────────────────

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string })?.detail;
    if (detail) return detail;
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred.';
}

export function mockDelay<T>(data: T, ms = 400): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}