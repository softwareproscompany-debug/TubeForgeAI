// TubeForge AI API client — fetch wrapper over the backend contract.
// Base: NEXT_PUBLIC_API_URL + /api/v1. Auth: `Token <token>` from localStorage.

import type { ApiErrorBody, Paginated } from "./types";

export class ApiError extends Error {
  code: string;
  retryable: boolean;
  correlation_id: string;

  constructor(body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.retryable = body.retryable;
    this.correlation_id = body.correlation_id;
  }
}

const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tf_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("tf_token", token);
  else localStorage.removeItem("tf_token");
}

export function isAuthed(): boolean {
  return getToken() !== null;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = opts.auth === false ? null : getToken();
  if (token) headers["Authorization"] = `Token ${token}`;

  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method: opts.method || "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch (e) {
    throw new ApiError({
      code: "network_unreachable",
      message: `Cannot reach API at ${BASE}. Is the backend running?`,
      retryable: true,
      correlation_id: "client-side",
    });
  }

  if (res.status === 204) return undefined as unknown as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const err = data as { error?: ApiErrorBody } | null;
    if (err && err.error) throw new ApiError(err.error);
    throw new ApiError({
      code: `http_${res.status}`,
      message: `Request failed with status ${res.status}`,
      retryable: res.status >= 500,
      correlation_id: "unknown",
    });
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, auth = true) => request<T>(path, { auth }),
  post: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "POST", body, auth }),
  patch: <T>(path: string, body: unknown, auth = true) =>
    request<T>(path, { method: "PATCH", body, auth }),
  del: <T>(path: string, auth = true) => request<T>(path, { method: "DELETE", auth }),
};

export function asList<T>(data: Paginated<T> | T[]): T[] {
  if (Array.isArray(data)) return data;
  return data.results;
}

export function fmtUsd(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${n.toFixed(2)}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}
