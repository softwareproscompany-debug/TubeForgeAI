// TubeForge AI auth state — AuthContext provider + useAuth hook.
//
// Token handling is NOT duplicated here: lib/api.ts already persists the
// token under localStorage key "tf_token" and attaches
// `Authorization: Token <token>` to every request (auth defaults to true).
// This provider is the single place that *writes* the token (login, register,
// passkey ceremonies, logout) and hydrates the user via GET /auth/me.
//
// Backend note (verified against backend/core/views.py): LoginView returns
// { token, user: { id, username, email, first_name, last_name, date_joined } }.
// The register and passkey endpoints are specified (by the parallel backend
// track) as { token, user_id, username } — normalizeAuthResponse accepts
// both shapes so the frontend works against either.

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import { ApiError, api, getToken, setToken } from "./api";
import type { PasskeyInfo, User } from "./types";

// ── base64url helpers (WebAuthn JSON wire format) ────────────────────────────
// The server sends challenge / credential ids as base64url strings; the
// WebAuthn API needs raw bytes, and the ceremony responses must be sent back
// as base64url strings.

export function b64ToBytes(b64url: string): Uint8Array<ArrayBuffer> {
  const b64 = b64url.trim().replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob(padded);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

export function bytesToB64(bytes: ArrayBuffer | Uint8Array): string {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < u8.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, Array.from(u8.subarray(i, i + CHUNK)));
  }
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// ── WebAuthn JSON option shapes (server → browser conversion) ────────────────

export interface CreationOptionsJSON {
  challenge: string;
  rp: { name: string; id?: string };
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams?: Array<{ type: string; alg: number }>;
  timeout?: number;
  excludeCredentials?: Array<{ type: string; id: string; transports?: string[] }>;
  authenticatorSelection?: Record<string, unknown>;
  attestation?: string;
}

export interface RequestOptionsJSON {
  challenge: string;
  timeout?: number;
  rpId?: string;
  allowCredentials?: Array<{ type: string; id: string; transports?: string[] }>;
  userVerification?: string;
}

function toCreationOptions(o: CreationOptionsJSON): PublicKeyCredentialCreationOptions {
  return {
    rp: o.rp,
    user: {
      name: o.user.name,
      displayName: o.user.displayName,
      id: b64ToBytes(o.user.id),
    },
    challenge: b64ToBytes(o.challenge),
    pubKeyCredParams:
      o.pubKeyCredParams?.map((p) => ({
        ...p,
        type: p.type as PublicKeyCredentialType,
      })) ?? [],
    timeout: o.timeout,
    excludeCredentials: o.excludeCredentials?.map((c) => ({
      type: c.type as PublicKeyCredentialType,
      id: b64ToBytes(c.id),
      transports: c.transports as AuthenticatorTransport[] | undefined,
    })),
    authenticatorSelection:
      o.authenticatorSelection as AuthenticatorSelectionCriteria | undefined,
    attestation: o.attestation as AttestationConveyancePreference | undefined,
  };
}

function toRequestOptions(o: RequestOptionsJSON): PublicKeyCredentialRequestOptions {
  return {
    challenge: b64ToBytes(o.challenge),
    timeout: o.timeout,
    rpId: o.rpId,
    allowCredentials: o.allowCredentials?.map((c) => ({
      type: c.type as PublicKeyCredentialType,
      id: b64ToBytes(c.id),
      transports: c.transports as AuthenticatorTransport[] | undefined,
    })),
    userVerification: o.userVerification as UserVerificationRequirement | undefined,
  };
}

interface RegistrationCredentialJSON {
  id: string;
  rawId: string;
  type: string;
  response: { clientDataJSON: string; attestationObject: string };
}

interface AssertionCredentialJSON {
  id: string;
  rawId: string;
  type: string;
  response: {
    clientDataJSON: string;
    authenticatorData: string;
    signature: string;
    userHandle: string | null;
  };
}

function serializeRegistration(cred: PublicKeyCredential): RegistrationCredentialJSON {
  const r = cred.response as AuthenticatorAttestationResponse;
  return {
    id: cred.id,
    rawId: bytesToB64(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bytesToB64(r.clientDataJSON),
      attestationObject: bytesToB64(r.attestationObject),
    },
  };
}

function serializeAssertion(cred: PublicKeyCredential): AssertionCredentialJSON {
  const r = cred.response as AuthenticatorAssertionResponse;
  return {
    id: cred.id,
    rawId: bytesToB64(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bytesToB64(r.clientDataJSON),
      authenticatorData: bytesToB64(r.authenticatorData),
      signature: bytesToB64(r.signature),
      userHandle: r.userHandle ? bytesToB64(r.userHandle) : null,
    },
  };
}

// ── token-response normalization ─────────────────────────────────────────────

interface TokenResponseJSON {
  token?: string;
  user?: Partial<User> & Record<string, unknown>;
  user_id?: string | number;
  username?: string;
  email?: string;
}

// ── context ──────────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  authed: boolean;
  webAuthnSupported: boolean;
  login: (username: string, password: string) => Promise<User>;
  register: (username: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  passkeyLogin: (username: string) => Promise<User>;
  passkeyRegister: (name: string) => Promise<PasskeyInfo>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [loading, setLoading] = useState(true);
  const [webAuthnSupported, setWebAuthnSupported] = useState(false);

  const applyTokenResponse = useCallback((res: TokenResponseJSON): User => {
    if (!res || typeof res.token !== "string" || !res.token) {
      throw new Error("Sign-in succeeded but the server did not return a token.");
    }
    const u = res.user ?? {};
    const next: User = {
      id: String(u.id ?? res.user_id ?? ""),
      username: String(u.username ?? res.username ?? ""),
      email: String(u.email ?? res.email ?? ""),
      first_name: String(u.first_name ?? ""),
      last_name: String(u.last_name ?? ""),
      date_joined: String(u.date_joined ?? ""),
    };
    if (!next.username) {
      throw new Error("Sign-in succeeded but the server did not return a user.");
    }
    setToken(res.token);
    setTokenState(res.token);
    setUser(next);
    return next;
  }, []);

  const clearSession = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const t = getToken();
    if (!t) {
      setUser(null);
      setTokenState(null);
      return null;
    }
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
      setTokenState(t);
      return me;
    } catch (e) {
      // Token rejected server-side (rotated, deleted) — drop it. Network
      // failures keep the token so a backend outage doesn't log users out.
      if (e instanceof ApiError && e.code === "http_401") clearSession();
      return null;
    }
  }, [clearSession]);

  const login = useCallback(
    async (username: string, password: string): Promise<User> => {
      const res = await api.post<TokenResponseJSON>(
        "/auth/login",
        { username, password },
        false
      );
      return applyTokenResponse(res);
    },
    [applyTokenResponse]
  );

  const register = useCallback(
    async (username: string, email: string, password: string): Promise<User> => {
      const res = await api.post<TokenResponseJSON>(
        "/auth/register",
        { username, email, password },
        false
      );
      return applyTokenResponse(res);
    },
    [applyTokenResponse]
  );

  const logout = useCallback(async (): Promise<void> => {
    // Best effort: the backend deletes the token; a 401 here just means the
    // token is already dead, which is the outcome we want anyway.
    try {
      await api.post("/auth/logout");
    } catch {
      /* already logged out server-side */
    }
    clearSession();
  }, [clearSession]);

  const requireWebAuthn = () => {
    if (typeof window === "undefined" || !window.PublicKeyCredential) {
      throw new Error(
        "Passkeys are not supported in this browser. Use a modern browser over HTTPS or localhost."
      );
    }
  };

  const passkeyLogin = useCallback(
    async (username: string): Promise<User> => {
      requireWebAuthn();
      const begin = await api.post<{ options: RequestOptionsJSON }>(
        "/auth/passkey/authenticate/begin",
        { username },
        false
      );
      const cred = (await navigator.credentials.get({
        publicKey: toRequestOptions(begin.options),
      })) as PublicKeyCredential | null;
      if (!cred) throw new Error("Passkey sign-in was cancelled.");
      const finish = await api.post<TokenResponseJSON>(
        "/auth/passkey/authenticate/finish",
        { username, credential: serializeAssertion(cred) },
        false
      );
      return applyTokenResponse(finish);
    },
    [applyTokenResponse]
  );

  const passkeyRegister = useCallback(async (name: string): Promise<PasskeyInfo> => {
    requireWebAuthn();
    const begin = await api.post<{ options: CreationOptionsJSON }>(
      "/auth/passkey/register/begin",
      { name }
    );
    const cred = (await navigator.credentials.create({
      publicKey: toCreationOptions(begin.options),
    })) as PublicKeyCredential | null;
    if (!cred) throw new Error("Passkey registration was cancelled.");
    return api.post<PasskeyInfo>("/auth/passkey/register/finish", {
      credential: serializeRegistration(cred),
    });
  }, []);

  // Hydrate on mount: existing token → /auth/me.
  useEffect(() => {
    let alive = true;
    setWebAuthnSupported(
      typeof window !== "undefined" && !!window.PublicKeyCredential
    );
    (async () => {
      await refreshUser();
      if (alive) setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [refreshUser]);

  const value: AuthContextValue = {
    user,
    token,
    loading,
    authed: !!user && !!token,
    webAuthnSupported,
    login,
    register,
    logout,
    refreshUser,
    passkeyLogin,
    passkeyRegister,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Re-exported so pages can read backend error messages without importing lib/api.
export { ApiError };
