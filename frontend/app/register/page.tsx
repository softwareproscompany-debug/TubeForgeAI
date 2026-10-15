// Registration page: client-side validation, auto-login on success.
// There is no /dashboard or /onboarding route in this app, so a successful
// registration lands on /overview (the app home).

"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, useAuth } from "../../lib/auth";
import {
  AuthCard,
  FormError,
  FormSuccess,
  TextField,
  errorMessage,
  primaryBtnCls,
} from "../../components/AuthBits";

export default function RegisterPage() {
  const { register, loading, authed } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const redirectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!loading && authed) router.replace("/overview");
    return () => {
      if (redirectTimer.current) clearTimeout(redirectTimer.current);
    };
  }, [loading, authed, router]);

  if (loading || authed) {
    return (
      <AuthCard title="Create account">
        <p className="text-sm text-studio-muted text-center animate-pulse">
          Checking session…
        </p>
      </AuthCard>
    );
  }

  const valid =
    username.trim().length > 0 &&
    /.+@.+\..+/.test(email.trim()) &&
    password.length >= 8 &&
    password === confirm;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!valid) {
      if (password.length < 8) setError("Password must be at least 8 characters.");
      else if (password !== confirm) setError("Passwords do not match.");
      else setError("Please fill in all fields with a valid email address.");
      return;
    }
    setBusy(true);
    try {
      // The register response carries a token — the auth provider stores it,
      // so the user is signed in immediately.
      await register(username.trim(), email.trim(), password);
      setDone(true);
      redirectTimer.current = setTimeout(() => router.push("/overview"), 1200);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : errorMessage(err, "Registration failed.")
      );
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthCard title="Create account">
        <FormSuccess message="Account created — redirecting to your studio…" />
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create account"
      subtitle="Spin up your private YouTube operating system."
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <FormError message={error} />
        <TextField
          id="register-username"
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          placeholder="your-username"
          required
        />
        <TextField
          id="register-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          placeholder="you@example.com"
          required
        />
        <TextField
          id="register-password"
          label="Password (min 8 characters)"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          placeholder="••••••••"
          minLength={8}
          required
        />
        <TextField
          id="register-confirm"
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          placeholder="••••••••"
          required
        />
        <button type="submit" disabled={busy || !valid} className={primaryBtnCls}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-sm text-center text-studio-muted">
        Already have an account?{" "}
        <Link href="/login" className="text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
