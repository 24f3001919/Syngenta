import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { Rep } from '../types';
import { getMe, refreshAccessToken, logoutApi } from '../api/auth';

interface AuthContextValue {
  rep: Rep | null;
  token: string | null;
  isLoading: boolean;
  login: (token: string, rep: Rep) => void;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [rep, setRep] = useState<Rep | null>(() => {
    try {
      const stored = localStorage.getItem('rep');
      return stored ? (JSON.parse(stored) as Rep) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [isLoading, setIsLoading] = useState(true);

  // On mount — verify session is still valid.
  // Three cases:
  //   1. Access token present → /auth/me to verify
  //   2. No access token but refresh cookie may exist → try silent refresh
  //   3. Both fail → unauthenticated
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      // Case 1 — have token, verify it
      if (token) {
        try {
          const me = await getMe();
          if (!cancelled) {
            setRep(me);
            localStorage.setItem('rep', JSON.stringify(me));
          }
        } catch {
          // Token bad — but interceptor in client.ts will already have tried
          // a refresh. If we got here, refresh failed too. Clear everything.
          if (!cancelled) {
            setToken(null);
            setRep(null);
            localStorage.removeItem('access_token');
            localStorage.removeItem('rep');
          }
        } finally {
          if (!cancelled) setIsLoading(false);
        }
        return;
      }

      // Case 2 — no access token; refresh cookie might still be valid (e.g.
      // user closed the tab and came back within 30 days). Try once.
      try {
        const fresh = await refreshAccessToken();
        if (!cancelled && fresh) {
          setToken(fresh.access_token);
          setRep(fresh.rep);
          localStorage.setItem('access_token', fresh.access_token);
          localStorage.setItem('rep', JSON.stringify(fresh.rep));
        }
      } catch {
        // No valid refresh cookie either → unauthenticated, that's fine.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    bootstrap();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback((newToken: string, newRep: Rep) => {
    localStorage.setItem('access_token', newToken);
    localStorage.setItem('rep', JSON.stringify(newRep));
    setToken(newToken);
    setRep(newRep);
  }, []);

  const logout = useCallback(async () => {
    // Best-effort server-side revoke. Always proceed with client cleanup.
    try {
      await logoutApi();
    } catch {
      // Server unreachable — proceed anyway
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('rep');
    setToken(null);
    setRep(null);
  }, []);

  const refreshMe = useCallback(async () => {
    const me = await getMe();
    setRep(me);
    localStorage.setItem('rep', JSON.stringify(me));
  }, []);

  return (
    <AuthContext.Provider value={{ rep, token, isLoading, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}