import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "./lib/api";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshMe() {
    try {
      const profile = await api.me();
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
  }, []);

  const value = useMemo(() => ({
    user,
    loading,
    isAdmin: user?.role === "admin",
    async login(data) {
      await api.login(data);
      return refreshMe();
    },
    async register(data) {
      await api.register(data);
      return refreshMe();
    },
    async logout() {
      await api.logout();
      setUser(null);
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
