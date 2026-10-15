"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api, asList } from "../../../lib/api";
import type { Paginated, PasskeyInfo } from "../../../lib/types";
import { useAuth } from "../../../lib/auth";

export default function SettingsPage() {
  const {
    user,
    loading,
    authed,
    login,
    logout,
    passkeyRegister,
    webAuthnSupported,
  } = useAuth();

  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // login form (only shown when not signed in)
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);

  // profile
  const [displayName, setDisplayName] = useState("");

  // security
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");

  // passkeys
  const [passkeys, setPasskeys] = useState<PasskeyInfo[]>([]);
  const [pkLoading, setPkLoading] = useState(false);
  const [pkName, setPkName] = useState("");
  const [pkBusy, setPkBusy] = useState(false);

  useEffect(() => {
    setDisplayName(user?.first_name || user?.username || user?.email || "");
  }, [user]);

  const loadPasskeys = async () => {
    if (!authed) return;
    setPkLoading(true);
    try {
      const data = await api.get<PasskeyInfo[] | Paginated<PasskeyInfo>>(
        "/auth/passkeys"
      );
      setPasskeys(asList(data));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load passkeys.");
    } finally {
      setPkLoading(false);
    }
  };

  useEffect(() => {
    if (authed) loadPasskeys();
    else setPasskeys([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed]);

  const onLogin = async () => {
    setError(null);
    setMsg(null);
    setLoginBusy(true);
    try {
      const u = await login(username, password);
      setMsg(`Signed in as ${u.username}. Token stored in localStorage ('tf_token').`);
      setUsername("");
      setPassword("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed.");
    } finally {
      setLoginBusy(false);
    }
  };

  const onLogout = async () => {
    await logout();
    setMsg("Logged out. Token cleared.");
  };

  const saveProfile = async () => {
    setError(null);
    setMsg(null);
    try {
      await api.patch("/auth/me", { display_name: displayName });
      setMsg("Profile updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    }
  };

  const changePassword = async () => {
    setError(null);
    setMsg(null);
    try {
      await api.post("/auth/change-password", { current_password: currentPw, new_password: newPw });
      setCurrentPw("");
      setNewPw("");
      setMsg("Password changed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Password change failed.");
    }
  };

  const addPasskey = async () => {
    setError(null);
    setMsg(null);
    setPkBusy(true);
    try {
      const created = await passkeyRegister(pkName.trim() || "Passkey");
      setPkName("");
      await loadPasskeys();
      setMsg(`Passkey "${created.name}" registered.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Passkey registration failed.");
    } finally {
      setPkBusy(false);
    }
  };

  const deletePasskey = async (id: string, name: string) => {
    if (!window.confirm(`Remove passkey "${name}"? You can re-register it later.`)) return;
    setError(null);
    setMsg(null);
    try {
      await api.del(`/auth/passkeys/${id}`);
      await loadPasskeys();
      setMsg(`Passkey "${name}" removed.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove passkey.");
    }
  };

  return (
    <div className="space-y-5 max-w-2xl">
      <h1 className="text-xl font-semibold text-studio-text">Settings</h1>
      {msg && <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/40 rounded p-3">{msg}</div>}
      {error && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/40 rounded p-3">{error}</div>}

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-studio-text">Billing</h2>
          <Link href="/settings/billing" className="text-sm text-accent hover:underline">
            Manage billing →
          </Link>
        </div>
        <p className="text-sm text-studio-muted">
          View your plan, usage, and upgrade to Pro or Enterprise.
        </p>
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">Account</h2>
        {loading ? (
          <p className="text-sm text-studio-muted animate-pulse">Checking session…</p>
        ) : authed && user ? (
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm">
              <div className="text-studio-text font-medium">{user.username}</div>
              <div className="text-studio-muted text-xs">{user.email}</div>
              <div className="text-studio-faint text-xs mt-1">
                API calls use header <span className="font-mono">Authorization: Token …</span>
              </div>
            </div>
            <button onClick={onLogout} className="text-sm px-3 py-1.5 rounded-md border border-studio-border text-studio-text hover:border-red-400/60 shrink-0">
              Log out
            </button>
          </div>
        ) : (
          <div className="space-y-3 text-sm">
            <label className="block">
              <span className="text-studio-muted text-xs">Username</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className={cls} />
            </label>
            <label className="block">
              <span className="text-studio-muted text-xs">Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className={cls} />
            </label>
            <button onClick={onLogin} disabled={!username || !password || loginBusy}
              className="bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50">
              {loginBusy ? "Signing in…" : "Log in"}
            </button>
          </div>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">Profile</h2>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-studio-muted text-xs">Display name</span>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={cls} />
          </label>
          <button onClick={saveProfile} disabled={!authed}
            className="bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50">
            Save profile
          </button>
        </div>
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">Security</h2>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-studio-muted text-xs">Current password</span>
            <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} autoComplete="current-password" className={cls} />
          </label>
          <label className="block">
            <span className="text-studio-muted text-xs">New password</span>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoComplete="new-password" className={cls} />
          </label>
          <button onClick={changePassword} disabled={!authed || !currentPw || !newPw}
            className="bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50">
            Change password
          </button>
          <p className="text-xs text-studio-faint">
            Sessions are token-based; logging out clears the token from this browser only. Rotate credentials if a device is lost.
          </p>
        </div>
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-1">Passkeys</h2>
        <p className="text-xs text-studio-faint mb-4">
          Passwordless sign-in for this account. Works with platform authenticators
          (Touch ID, Windows Hello) and security keys.
        </p>
        {!webAuthnSupported ? (
          <p className="text-sm text-studio-muted">
            This browser doesn&apos;t support passkeys (WebAuthn needs a modern
            browser over HTTPS or localhost).
          </p>
        ) : !authed ? (
          <p className="text-sm text-studio-muted">Sign in above to manage passkeys.</p>
        ) : (
          <div className="space-y-4 text-sm">
            {pkLoading ? (
              <p className="text-studio-muted animate-pulse">Loading passkeys…</p>
            ) : passkeys.length === 0 ? (
              <p className="text-studio-muted">No passkeys registered yet.</p>
            ) : (
              <ul className="divide-y divide-studio-border border border-studio-border rounded-md">
                {passkeys.map((pk) => (
                  <li key={pk.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
                    <div>
                      <div className="text-studio-text">{pk.name}</div>
                      <div className="text-xs text-studio-faint">
                        Registered {new Date(pk.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button
                      onClick={() => deletePasskey(pk.id, pk.name)}
                      className="text-xs px-2.5 py-1.5 rounded-md border border-studio-border text-studio-muted hover:text-red-300 hover:border-red-400/60"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex gap-2">
              <label className="flex-1">
                <span className="sr-only">Friendly name for the new passkey</span>
                <input
                  value={pkName}
                  onChange={(e) => setPkName(e.target.value)}
                  placeholder='Friendly name, e.g. "MacBook Touch ID"'
                  className={cls}
                  maxLength={100}
                />
              </label>
              <button
                onClick={addPasskey}
                disabled={pkBusy}
                className="bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50 shrink-0"
              >
                {pkBusy ? "Waiting…" : "Add passkey"}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">System</h2>
        <div className="text-sm text-studio-muted space-y-1">
          <div>API base: <span className="font-mono text-xs text-studio-text">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1</span></div>
          <div className="text-xs text-studio-faint">
            Budgets are enforced server-side per resource (local GPU, cloud GPU, paid API spend, storage) — never as a single combined credit.
          </div>
        </div>
      </section>
    </div>
  );
}

const cls = "mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text";
