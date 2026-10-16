// Sign-in page: password login + optional passkey login (WebAuthn).

"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, useAuth } from "../../lib/auth";
import {
  AuthCard,
  FormError,
  TextField,
  errorMessage,
  ghostBtnCls,
  primaryBtnCls,
} from "../../components/AuthBits";

export default function LoginPage() {
  const { login, passkeyLogin, webAuthnSupported, loading, authed } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"password" | "passkey" | null>(null);

  useEffect(() => {
    if (!loading && authed) router.replace("/overview");
  }, [loading, authed, router]);

  if (loading || authed) {
    return (
      <AuthCard title="Sign in">
        <p className="text-sm text-studio-muted text-center animate-pulse">
          Checking session…
        </p>
      </AuthCard>
    );
  }

  const onPasswordLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy("password");
    try {
      await login(username.trim(), password);
      router.push("/overview");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : errorMessage(err, "Sign-in failed.")
      );
    } finally {
      setBusy(null);
    }
  };

  const onPasskeyLogin = async () => {
    setError(null);
    setBusy("passkey");
    try {
      await passkeyLogin(username.trim());
      router.push("/overview");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : errorMessage(err, "Passkey sign-in failed.")
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <AuthCard
      title="Sign in"
      subtitle="Welcome back to your YouTube studio OS."
    >
      <form onSubmit={onPasswordLogin} className="space-y-4">
        <FormError message={error} />
        <TextField
          id="login-username"
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username webauthn"
          placeholder="your-username"
          required
        />
        <TextField
          id="login-password"
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder="••••••••"
          required
        />
        <button
          type="submit"
          disabled={busy !== null || !username.trim() || !password}
          className={primaryBtnCls}
        >
          {busy === "password" ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {webAuthnSupported && (
        <div className="mt-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="flex-1 h-px bg-studio-border" />
            <span className="text-xs text-studio-faint">or</span>
            <span className="flex-1 h-px bg-studio-border" />
          </div>
          <button
            type="button"
            onClick={onPasskeyLogin}
            disabled={busy !== null || !username.trim()}
            className={ghostBtnCls}
            title="Enter your username above, then sign in with your passkey"
          >
            {busy === "passkey" ? "Waiting for passkey…" : "🔑 Sign in with passkey"}
          </button>
          {!username.trim() && (
            <p className="mt-2 text-xs text-studio-faint text-center">
              Enter your username first to use a passkey.
            </p>
          )}
        </div>
      )}

      <div className="mt-6 flex items-center justify-between text-sm">
        <Link href="/register" className="text-accent hover:underline touch-manipulation py-2">
          Create an account
        </Link>
        <Link
          href="/forgot-password"
          className="text-studio-muted hover:text-studio-text hover:underline touch-manipulation py-2"
        >
          Forgot password?
        </Link>
      </div>
    </AuthCard>
  );
}
