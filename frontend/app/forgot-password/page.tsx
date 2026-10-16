// Password reset: two steps (request token → confirm with new password).
// Email delivery is not wired on the backend yet — the reset token is logged
// to the backend console, so the UI says so plainly.

"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { ApiError, api } from "../../lib/api";
import {
  AuthCard,
  FormError,
  FormSuccess,
  TextField,
  errorMessage,
  primaryBtnCls,
} from "../../components/AuthBits";

type Step = "request" | "confirm" | "done";

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onRequest = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.post("/auth/password-reset/request", { email: email.trim() }, false);
      setStep("confirm");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : errorMessage(err, "Could not start the reset.")
      );
    } finally {
      setBusy(false);
    }
  };

  const confirmValid =
    token.trim().length > 0 &&
    newPassword.length >= 8 &&
    newPassword === confirm;

  const onConfirm = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!confirmValid) {
      setError("Token is required, and the new password must be at least 8 characters and match.");
      return;
    }
    setBusy(true);
    try {
      await api.post(
        "/auth/password-reset/confirm",
        { email: email.trim(), token: token.trim(), new_password: newPassword },
        false
      );
      setStep("done");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : errorMessage(err, "Could not reset the password.")
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Reset password"
      subtitle="Two quick steps and you're back in."
    >
      <FormError message={error} />

      {step === "request" && (
        <form onSubmit={onRequest} className="space-y-4">
          <TextField
            id="reset-email"
            label="Account email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            placeholder="you@example.com"
            required
          />
          <button
            type="submit"
            disabled={busy || !/.+@.+\..+/.test(email.trim())}
            className={primaryBtnCls}
          >
            {busy ? "Sending…" : "Send reset token"}
          </button>
          <p className="text-xs text-studio-faint text-center">
            Email delivery isn&apos;t wired yet — the reset token is written to
            the backend console/log in dev.
          </p>
        </form>
      )}

      {step === "confirm" && (
        <form onSubmit={onConfirm} className="space-y-4">
          <FormSuccess
            message="Token requested — grab it from the backend console/log and enter it below."
          />
          <TextField
            id="reset-token"
            label="Reset token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="one-time-code"
            placeholder="paste token here"
            required
          />
          <TextField
            id="reset-new-password"
            label="New password (min 8 characters)"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            placeholder="••••••••"
            minLength={8}
            required
          />
          <TextField
            id="reset-confirm"
            label="Confirm new password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            placeholder="••••••••"
            required
          />
          <button type="submit" disabled={busy || !confirmValid} className={primaryBtnCls}>
            {busy ? "Resetting…" : "Set new password"}
          </button>
        </form>
      )}

      {step === "done" && (
        <div className="space-y-4">
          <FormSuccess message="Password updated — you can sign in with it now." />
          <Link href="/login" className={primaryBtnCls}>
            Back to sign in
          </Link>
        </div>
      )}

      {step !== "done" && (
        <p className="mt-6 text-sm text-center text-studio-muted">
          <Link href="/login" className="text-accent hover:underline touch-manipulation inline-block py-2">
            ← Back to sign in
          </Link>
        </p>
      )}
    </AuthCard>
  );
}
