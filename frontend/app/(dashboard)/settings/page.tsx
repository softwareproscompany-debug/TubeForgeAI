"use client";

import { useEffect, useState } from "react";
import { api, getToken, setToken } from "../../../lib/api";

export default function SettingsPage() {
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);

  // profile
  const [displayName, setDisplayName] = useState("");

  // security
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");

  useEffect(() => {
    setAuthed(!!getToken());
    (async () => {
      try {
        const me = await api.get<{ display_name?: string }>("/auth/me").catch(() => null);
        if (me?.display_name) setDisplayName(me.display_name);
      } catch { /* optional */ }
    })();
  }, []);

  const login = async () => {
    setError(null);
    setMsg(null);
    try {
      const res = await api.post<{ token: string; user: { display_name: string } }>("/auth/login", { email, password }, false);
      setToken(res.token);
      setAuthed(true);
      setDisplayName(res.user.display_name);
      setMsg("Logged in. Token stored in localStorage ('tf_token').");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed.");
    }
  };

  const logout = () => {
    setToken(null);
    setAuthed(false);
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

  return (
    <div className="space-y-5 max-w-2xl">
      <h1 className="text-xl font-semibold text-studio-text">Settings</h1>
      {msg && <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/40 rounded p-3">{msg}</div>}
      {error && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/40 rounded p-3">{error}</div>}

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">Account</h2>
        {authed ? (
          <div className="flex items-center justify-between">
            <span className="text-sm text-studio-muted">Signed in — API calls use header <span className="font-mono text-xs">Authorization: Token …</span></span>
            <button onClick={logout} className="text-sm px-3 py-1.5 rounded-md border border-studio-border text-studio-text hover:border-red-400/60">
              Log out
            </button>
          </div>
        ) : (
          <div className="space-y-3 text-sm">
            <label className="block">
              <span className="text-studio-muted text-xs">Email</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={cls} />
            </label>
            <label className="block">
              <span className="text-studio-muted text-xs">Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={cls} />
            </label>
            <button onClick={login} disabled={!email || !password}
              className="bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50">
              Log in
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
            <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} className={cls} />
          </label>
          <label className="block">
            <span className="text-studio-muted text-xs">New password</span>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} className={cls} />
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
