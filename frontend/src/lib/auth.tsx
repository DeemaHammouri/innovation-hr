"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, tokens, type User } from "./api";
import { useI18n, type Lang } from "./i18n";

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  /** True after the server refused a refresh: the session ran out, as opposed to a deliberate sign out. */
  sessionExpired: boolean;
  setUser: (user: User) => void;
};

// Kept in memory only, and only while a forced password change is pending, so the new password can be
// compared with the temporary one as the person types. A page reload forgets it.
let temporaryPassword = "";
export const getTemporaryPassword = () => temporaryPassword;
export const forgetTemporaryPassword = () => {
  temporaryPassword = "";
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const { setLang } = useI18n();
  const setLangRef = useRef(setLang);
  useEffect(() => {
    setLangRef.current = setLang;
  }, [setLang]);
  // The language saved on the account wins once the person is known.
  const applyLanguage = useCallback((u: User) => {
    const saved: Lang = u.preferred_language === "ar" ? "ar" : "en";
    if (document.documentElement.lang !== saved) setLangRef.current(saved);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (tokens.access || tokens.refresh) {
        try {
          const me = await api<User>("/auth/me/");
          if (!cancelled) {
            setUser(me);
            applyLanguage(me);
          }
        } catch {
          tokens.clear();
        }
      }
      if (!cancelled) setLoading(false);
    })();
    const onSignedOut = () => {
      setUser(null);
      setSessionExpired(true);
    };
    window.addEventListener("innovation:signed-out", onSignedOut);
    return () => {
      cancelled = true;
      window.removeEventListener("innovation:signed-out", onSignedOut);
    };
  }, [applyLanguage]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access: string; refresh: string; user: User }>("/auth/login/", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    tokens.set(res.access, res.refresh);
    temporaryPassword = res.user.must_change_password ? password : "";
    setSessionExpired(false);
    setUser(res.user);
    applyLanguage(res.user);
    return res.user;
  }, [applyLanguage]);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout/", { method: "POST", body: { refresh: tokens.refresh } });
    } catch {
      // Signing out locally still works if the server can't be reached.
    }
    tokens.clear();
    setSessionExpired(false);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, sessionExpired, setUser }), [user, loading, login, logout, sessionExpired]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Changes the language everywhere at once and, when someone is signed in, saves it on their account. */
export function useChangeLanguage() {
  const { setLang, lang } = useI18n();
  const { user, setUser } = useAuth();
  return useCallback(
    (next: Lang) => {
      if (next === lang) return;
      setLang(next);
      if (user) {
        api<User>("/auth/me/", { method: "PATCH", body: { preferred_language: next } })
          .then((updated) => setUser(updated))
          .catch(() => {
            // The page is already in the new language. The cookie keeps it; the account saves next time.
          });
      }
    },
    [lang, setLang, user, setUser],
  );
}

/** Signs out, then does a full page load so nothing from this person stays in memory. */
export function useSignOut() {
  const { logout } = useAuth();
  return useCallback(async () => {
    await logout();
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }, [logout]);
}
