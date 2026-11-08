"use client";
import { useCallback, useSyncExternalStore } from "react";
import { extraViews, navigationGroups } from "./navigation";
const valid = new Set([
  ...navigationGroups.flatMap((g) => g.items.map((i) => i.id)),
  ...extraViews.map((i) => i.id),
]);
/** URLs store navigation identifiers only, never staff credentials, notes or evidence bodies. */
export function useNavigation(defaultView = "dashboard") {
  const search = useSyncExternalStore(
    subscribe,
    () => window.location.search,
    () => "",
  );
  const params = new URLSearchParams(search);
  const target = params.get("view");
  const view = target && valid.has(target) ? target : defaultView;
  const reference = params.get("ref");
  const navigate = useCallback((next: string, ref?: string) => {
    if (!valid.has(next)) return;
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    if (ref) url.searchParams.set("ref", ref);
    else url.searchParams.delete("ref");
    window.history.pushState({}, "", url);
    window.dispatchEvent(new Event("workpaper:navigate"));
    document.getElementById("main-content")?.focus();
  }, []);
  const setView = useCallback(
    (next: React.SetStateAction<string>) =>
      navigate(typeof next === "function" ? next(view) : next),
    [navigate, view],
  );
  return { view, setView, navigate, reference };
}
function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener("workpaper:navigate", callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener("workpaper:navigate", callback);
  };
}
