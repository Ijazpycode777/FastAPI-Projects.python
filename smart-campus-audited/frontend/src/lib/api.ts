/**
 * API client: thin fetch wrapper with credentials, CSRF, JSON envelope handling,
 * and structured error throwing so TanStack Query can surface failures.
 */
import { API_BASE } from "./constants";

export { API_BASE };

export class ApiError extends Error {
  status: number;
  code: string;
  details: { field: string; message: string }[];
  constructor(status: number, code: string, message: string, details: { field: string; message: string }[] = []) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.name = "ApiError";
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string) {
  csrfToken = token;
}

async function refreshCsrf(): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/auth/csrf`, { method: "POST", credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      if (data?.csrf_token) setCsrfToken(data.csrf_token);
    }
  } catch {
    /* ignore — best-effort */
  }
}

export type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  raw?: boolean; // return Response (for downloads)
  headers?: Record<string, string>;
};

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  if (!query) return `${API_BASE}${path}`;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${API_BASE}${path}?${qs}` : `${API_BASE}${path}`;
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = (opts.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json", ...(opts.headers ?? {}) };
  const isUnsafe = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  if (isUnsafe) {
    if (!csrfToken) await refreshCsrf();
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
    if (opts.body !== undefined && !(opts.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
  }

  const init: RequestInit = { method, headers, credentials: "include" };
  if (opts.body !== undefined) {
    init.body = opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), init);
  } catch (e) {
    throw new ApiError(0, "NETWORK", "Network error — please check your connection.");
  }

  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Session expired — surface so the app can redirect to login.
    throw new ApiError(401, "UNAUTHENTICATED", "Your session has expired. Please sign in again.");
  }

  if (opts.raw) return res as unknown as T;

  if (res.status === 204) return undefined as unknown as T;

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const envelope = payload as { error?: { code?: string; message?: string; details?: { field: string; message: string }[] } };
    const err = envelope?.error;
    if (res.status === 403 && (err?.code === "CSRF_FAILED" || err?.message?.includes("CSRF"))) {
      // Refresh CSRF once and retry.
      await refreshCsrf();
      if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
      res = await fetch(buildUrl(path, opts.query), init);
      if (res.ok) {
        const retryText = await res.text();
        return (retryText ? JSON.parse(retryText) : undefined) as T;
      }
    }
    throw new ApiError(res.status, err?.code ?? "ERROR", err?.message ?? `Request failed (${res.status})`, err?.details ?? []);
  }
  return payload as T;
}

export const http = {
  get: <T>(path: string, query?: RequestOptions["query"]) => api<T>(path, { query }),
  post: <T>(path: string, body?: unknown) => api<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => api<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => api<T>(path, { method: "PUT", body }),
  del: <T>(path: string) => api<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => api<T>(path, { method: "POST", body: form }),
  raw: (path: string, opts: RequestOptions = {}) => api<Response>(path, { ...opts, raw: true }),
};
