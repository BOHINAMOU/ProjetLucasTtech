import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { ApiError, get, getToken, post, saveToken, setUnauthorizedHandler } from './api';
import { registerForPush, unregisterPush } from './push';
import type { AppConfig, Kind, User } from './types';

interface AuthState {
  user: User | null;
  kind: Kind;
  loading: boolean;
  config: AppConfig | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: Record<string, unknown>) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<User | null>;
  chooseType: (type: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const started = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const me = await get<User>('me');
      setUser(me);
      return me;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        await saveToken(null);
        setUser(null);
      }
      return null;
    }
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      get<AppConfig>('config', { auth: false }).then(setConfig).catch(() => {});
      if (await getToken()) {
        const me = await refresh();
        if (me) registerForPush();
      }
      setLoading(false);
    })();
  }, [refresh]);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const enter = useCallback(async (res: { token: string; user: User }) => {
    await saveToken(res.token);
    setUser(res.user);
    registerForPush();
    refresh();
  }, [refresh]);

  const value = useMemo<AuthState>(() => ({
    user,
    kind: user ? user.kind : 'anonymous',
    loading,
    config,
    refresh,
    login: async (email, password) => {
      enter(await post('auth/login', { email, password }, { auth: false }));
    },
    register: async (data) => {
      enter(await post('auth/register', data, { auth: false }));
    },
    logout: async () => {
      await unregisterPush();
      try {
        await post('auth/logout');
      } catch {
        /* le jeton est de toute façon supprimé sur le téléphone */
      }
      await saveToken(null);
      setUser(null);
    },
    chooseType: async (type) => {
      await post('me/account-type', { account_type: type });
      await refresh();
    },
  }), [user, loading, config, refresh, enter]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth doit être utilisé dans <AuthProvider>');
  return ctx;
}

/** Page d'accueil (groupe de routes) selon le type de compte. */
export function homeFor(kind: Kind): string {
  switch (kind) {
    case 'candidate': return '/(candidate)';
    case 'employer': return '/(employer)';
    case 'member': return '/(member)';
    case 'undefined': return '/choose-type';
    default: return '/login';
  }
}
