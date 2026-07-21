import { createContext, useContext, useEffect, useMemo, useState } from "react";

const RouterContext = createContext(null);

export function RouterProvider({ children }) {
  const [location, setLocation] = useState(() => window.location);

  useEffect(() => {
    const update = () => setLocation(window.location);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  const value = useMemo(() => ({
    location,
    navigate(to) {
      if (to === `${window.location.pathname}${window.location.search}${window.location.hash}`) return;
      window.history.pushState({}, "", to);
      setLocation(window.location);
      window.scrollTo({ top: 0, behavior: "instant" });
    }
  }), [location]);

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter() {
  const router = useContext(RouterContext);
  if (!router) throw new Error("useRouter must be used inside RouterProvider");
  return router;
}

export function Link({ to, children, onClick, ...props }) {
  const { navigate } = useRouter();
  return <a href={to} onClick={(event) => {
    onClick?.(event);
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.button !== 0) return;
    event.preventDefault();
    navigate(to);
  }} {...props}>{children}</a>;
}
