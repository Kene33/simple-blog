import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "./lib/api";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshMe() {
    try {
      const profile = await Promise.race([
        api.me(),
        new Promise((_, reject) => window.setTimeout(() => reject(new Error("Session check timeout")), 4000))
      ]);
      setUser(profile);
      return profile;
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshMe().catch(() => setUser(null));
    const clear = () => setUser(null);
    window.addEventListener("simple:auth-lost", clear);
    return () => window.removeEventListener("simple:auth-lost", clear);
  }, []);

  const value = useMemo(() => ({
    user,
    loading,
    isAdmin: user?.role === "admin",
    isModerator: user?.role === "moderator",
    isStaff: user?.role === "admin" || user?.role === "moderator",
    async login(data) {
      await api.login(data);
      return refreshMe();
    },
    async register(data) {
      await api.register(data);
      return refreshMe();
    },
    async logout() {
      try {
        await api.logout();
      } finally {
        setUser(null);
      }
    },
    refreshMe
  }), [user, loading]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside SessionProvider");
  return session;
}
