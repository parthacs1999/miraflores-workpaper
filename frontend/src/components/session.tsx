"use client";
import { createContext, useContext } from "react";
export type StaffIdentity = {
  id: string;
  name: string;
  role: string;
  sensitive_data_clearance: boolean;
  assurance: string;
};
export const SessionContext = createContext<StaffIdentity | null>(null);
export const useWorkpaperIdentity = () => useContext(SessionContext);
let csrf = "";
let epoch = 0;
let reveal = false;
let purpose = "";
export function sessionCredentials(token: string) {
  csrf = token;
  epoch++;
  reveal = false;
  purpose = "";
}
export function sensitiveAccess(enabled: boolean, reason: string) {
  reveal = enabled;
  purpose = reason;
  epoch++;
}
export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
) {
  const generation = epoch;
  const headers = new Headers(init.headers);
  if (init.method && !["GET", "HEAD"].includes(init.method.toUpperCase()))
    headers.set("X-CSRF-Token", csrf);
  if (reveal) {
    headers.set("X-Sensitive-Access", "reveal");
    headers.set("X-Access-Purpose", purpose);
  }
  const response = await fetch(input, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (init.signal?.aborted)
    throw new DOMException("Request cancelled", "AbortError");
  if (generation !== epoch)
    throw new Error(
      "Session or sensitive-access mode changed; response discarded",
    );
  if (response.status === 401)
    window.dispatchEvent(new Event("workpaper:access-lost"));
  return response;
}
