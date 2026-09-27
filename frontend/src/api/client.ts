/** Fetch wrapper: bearer auth, silent refresh on 401 (one shared refresh in flight), readable errors. */
import type { TokenResponse } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";
const ACCESS = "tb.access";
const REFRESH = "tb.refresh";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const tokens = {
  get access() { return sessionStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  save(t: Pick<TokenResponse, "access_token" | "refresh_token">) {
    sessionStorage.setItem(ACCESS, t.access_token);
    localStorage.setItem(REFRESH, t.refresh_token);
  },
  clear() { sessionStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); },
};

let onLogout: () => void = () => {};
export function setLogoutHandler(fn: () => void) { onLogout = fn; }

let refreshing: Promise<boolean> | null = null;
export async function refreshSession(): Promise<boolean> {
  const rt = tokens.refresh;
  if (!rt) return false;
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }),
  }).then(async (r) => {
    if (!r.ok) return false;
    tokens.save(await r.json());
    return true;
  }).catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
  }
  if (status === 0) return "Can't reach the server. Check that the backend is running.";
  return `Request failed (${status})`;
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const run = () => fetch(`${BASE}${path}`, {
    method,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(auth && tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let res: Response;
  try {
    res = await run();
    if (res.status === 401 && auth) {
      if (await refreshSession()) res = await run();
      else { tokens.clear(); onLogout(); }
    }
  } catch {
    throw new ApiError(0, messageFrom(null, 0));
  }
  const text = await res.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status));
  return data as T;
}

export const get = <T,>(p: string) => api<T>(p);
export const post = <T,>(p: string, body?: unknown) => api<T>(p, { method: "POST", body: body ?? {} });
export const put = <T,>(p: string, body: unknown) => api<T>(p, { method: "PUT", body });
export const patch = <T,>(p: string, body: unknown) => api<T>(p, { method: "PATCH", body });
export const del = <T,>(p: string) => api<T>(p, { method: "DELETE" });

export function wsUrl(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  const base = configured ?? `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${BASE}`;
  return `${base}/ws?token=${encodeURIComponent(tokens.access ?? "")}`;
}
