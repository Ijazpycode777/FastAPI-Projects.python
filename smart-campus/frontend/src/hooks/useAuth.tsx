import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { http, setCsrfToken } from "@/lib/api";
import type { Profile } from "@/types";

interface AuthContextValue {
  profile: Profile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Profile>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const p = await http.get<Profile>("/auth/me");
      setProfile(p);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const p = await http.post<Profile & { csrf_token?: string }>("/auth/login", { email, password });
    // The backend rotates the CSRF cookie on login (session-fixation
    // protection). Sync the in-memory token from the response body so the
    // first state-changing request sends the correct token -- otherwise it
    // would send the stale pre-login token, 403, and depend on the
    // refresh/retry path (which can surface a misleading 'session expired').
    if (p.csrf_token) setCsrfToken(p.csrf_token);
    setProfile(p);
    // Drop any cached data from a previous session so the new user never sees
    // stale rows belonging to someone else.
    queryClient.clear();
    if (p.user.must_reset_password) {
      navigate("/change-password", { replace: true });
    }
    return p;
  }, [navigate, queryClient]);

  const logout = useCallback(async () => {
    try {
      await http.post("/auth/logout");
    } catch {
      /* ignore */
    }
    setProfile(null);
    // Drop cached user data on the way out.
    queryClient.clear();
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ profile, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
