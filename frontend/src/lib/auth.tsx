import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { User } from "./types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  setSession: (token: string, user: User) => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);
interface TokenResp { access_token: string; user: User }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      tokenStore.set(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    void refresh();
  }, [logout, refresh]);

  const setSession = useCallback((token: string, u: User) => {
    tokenStore.set(token);
    setUser(u);
  }, []);

  const value = useMemo<AuthCtx>(() => ({
    user, loading, logout, refresh, setSession,
    login: async (email, password) => {
      const r = await api<TokenResp>("/auth/login", { body: { email, password } });
      setSession(r.access_token, r.user);
    },
    register: async (name, email, password) => {
      const r = await api<TokenResp>("/auth/register", { body: { name, email, password } });
      setSession(r.access_token, r.user);
    },
  }), [user, loading, logout, refresh, setSession]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth fora do AuthProvider");
  return c;
}
