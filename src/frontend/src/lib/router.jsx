import { createContext, useContext, useEffect, useMemo, useState } from "react";

const RouterContext = createContext(null);
const currentLocation = () => ({ pathname: window.location.pathname, search: window.location.search, hash: window.location.hash });

export function RouterProvider({ children }) {
  const [location, setLocation] = useState(currentLocation);

  useEffect(() => {
    const update = () => setLocation(currentLocation());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  const value = useMemo(() => ({
    location,
    navigate(to, options = {}) {
      if (to === "/login" && !options.allowAuth) {
        window.dispatchEvent(new CustomEvent("simple:guest-action", { detail: { action: "продолжить" } }));
        return;
      }
      if (to === `${window.location.pathname}${window.location.search}${window.location.hash}`) return;
      window.history.pushState({}, "", to);
      setLocation(currentLocation());
      window.scrollTo({ top: 0, behavior: "instant" });
    },
    replace(to) {
      if (to === `${window.location.pathname}${window.location.search}${window.location.hash}`) return;
      window.history.replaceState({}, "", to);
      setLocation(currentLocation());
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
    navigate(to, { allowAuth: true });
  }} {...props}>{children}</a>;
}
