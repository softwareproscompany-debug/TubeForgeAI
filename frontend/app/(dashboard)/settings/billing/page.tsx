"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, asList, fmtDate, fmtUsd, getToken } from "../../../../lib/api";
import type {
  BillingUsage,
  SubscriptionTier,
  UserSubscription,
} from "../../../../lib/types";

function Err({ e, retry }: { e: Error; retry: () => void }) {
  return (
    <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-sm text-red-300">
      <div className="font-medium">Could not load billing</div>
      <div className="mt-1 text-red-300/80">{e.message}</div>
      <button onClick={retry} className="mt-2 text-xs underline hover:text-red-200">
        Retry
      </button>
    </div>
  );
}

function Meter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number;
}) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-studio-muted">
        <span>{label}</span>
        <span>
          {used} / {limit}
        </span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-studio-border/60 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-400" : "bg-accent"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function BillingPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tiers, setTiers] = useState<SubscriptionTier[]>([]);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams(window.location.search);
        if (params.get("checkout") === "success") {
          setNotice(
            "Checkout completed. Your plan will update once the payment is confirmed."
          );
        } else if (params.get("checkout") === "cancelled") {
          setNotice("Checkout was cancelled — no changes were made.");
        }
        const [tierList, subBody] = await Promise.all([
          api
            .get<SubscriptionTier[]>("/billing/tiers", !!getToken())
            .then((d) => asList(d)),
          api
            .get<{ subscription: UserSubscription; usage: BillingUsage }>(
              "/billing/subscription"
            )
            .catch(() => null),
        ]);
        if (!alive) return;
        setTiers(tierList);
        if (subBody) {
          setSubscription(subBody.subscription);
          setUsage(subBody.usage);
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e : new Error("Unknown error"));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  const startCheckout = async (tierName: string) => {
    setBusy(tierName);
    setNotice(null);
    try {
      const res = await api.post<{ checkout_url: string; stub: boolean }>(
        "/billing/checkout",
        { tier: tierName }
      );
      if (res.stub) {
        setNotice(
          "Stripe is not connected yet — this is a dev checkout stub, no real charge is possible."
        );
      }
      window.location.href = res.checkout_url;
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Checkout failed.");
      setBusy(null);
    }
  };

  const openPortal = async () => {
    setBusy("portal");
    setNotice(null);
    try {
      const res = await api.post<{ portal_url: string; stub: boolean }>(
        "/billing/portal",
        {}
      );
      if (res.stub) {
        setNotice(
          "Stripe is not connected yet — this is a dev portal stub."
        );
      }
      window.location.href = res.portal_url;
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Portal failed.");
      setBusy(null);
    }
  };

  if (loading) return <div className="text-studio-muted text-sm">Loading billing…</div>;
  if (error) return <Err e={error} retry={() => setNonce((n) => n + 1)} />;

  const currentTier = subscription?.tier?.name ?? "free";
  const statusColor =
    subscription?.status === "active"
      ? "text-emerald-300"
      : subscription?.status === "past_due"
        ? "text-amber-300"
        : "text-red-300";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-studio-text">Billing</h1>
          <p className="text-sm text-studio-muted mt-1">
            Plans, usage, and subscription management.
          </p>
        </div>
        <Link href="/settings" className="text-sm text-accent hover:underline min-h-[44px] inline-flex items-center">
          ← Back to settings
        </Link>
      </div>

      {notice && (
        <div className="bg-accent/10 border border-accent/40 rounded-lg p-4 text-sm text-studio-text">
          {notice}
        </div>
      )}

      {/* Current plan */}
      <div className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-studio-muted">
              Current plan
            </div>
            <div className="mt-1 text-2xl font-semibold text-studio-text">
              {subscription?.tier?.display_name ?? "Free"}
            </div>
            <div className="mt-1 text-sm">
              <span className={statusColor}>
                {subscription?.status ?? "unknown"}
              </span>
              {subscription?.current_period_end && (
                <span className="text-studio-muted">
                  {" "}
                  · renews {fmtDate(subscription.current_period_end)}
                </span>
              )}
            </div>
          </div>
          {subscription && currentTier !== "free" && (
            <button
              onClick={openPortal}
              disabled={busy !== null}
              className="px-4 py-2 min-h-[44px] rounded-lg border border-studio-border text-sm text-studio-text hover:border-accent/50 disabled:opacity-50"
            >
              {busy === "portal" ? "Opening…" : "Manage subscription"}
            </button>
          )}
        </div>
        {usage && (
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <Meter
              label="Projects"
              used={usage.projects_used}
              limit={usage.projects_limit}
            />
            <Meter
              label="Storage (GB)"
              used={usage.storage_gb_used}
              limit={usage.storage_gb_limit}
            />
            <Meter
              label="API calls / month"
              used={usage.api_calls_used}
              limit={usage.api_calls_limit}
            />
          </div>
        )}
      </div>

      {/* Pricing table */}
      <div>
        <h2 className="text-lg font-medium text-studio-text mb-3">Plans</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {tiers.map((tier) => {
            const isCurrent = tier.name === currentTier;
            return (
              <div
                key={tier.id}
                className={`bg-studio-panel border rounded-lg p-5 flex flex-col ${
                  isCurrent ? "border-accent/70" : "border-studio-border"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-studio-text">
                    {tier.display_name}
                  </div>
                  {isCurrent && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent">
                      Current
                    </span>
                  )}
                </div>
                <div className="mt-2">
                  <span className="text-3xl font-semibold text-studio-text">
                    {fmtUsd(tier.price_monthly_usd)}
                  </span>
                  <span className="text-sm text-studio-muted"> / month</span>
                </div>
                <ul className="mt-4 space-y-2 text-sm text-studio-muted flex-1">
                  {tier.features.map((f) => (
                    <li key={f} className="flex gap-2">
                      <span className="text-accent">✓</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-5">
                  {isCurrent ? (
                    <button
                      disabled
                      className="w-full px-4 py-2 min-h-[44px] rounded-lg text-sm border border-studio-border text-studio-faint cursor-default"
                    >
                      Current plan
                    </button>
                  ) : tier.name === "free" ? (
                    <div className="text-xs text-studio-faint text-center">
                      Downgrade or cancel from the customer portal once Stripe is
                      connected.
                    </div>
                  ) : (
                    <button
                      onClick={() => startCheckout(tier.name)}
                      disabled={busy !== null}
                      className="w-full px-4 py-2 min-h-[44px] rounded-lg text-sm font-medium bg-accent text-black hover:opacity-90 disabled:opacity-50"
                    >
                      {busy === tier.name ? "Starting…" : `Upgrade to ${tier.display_name}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-4 text-xs text-studio-faint">
          Cancel or downgrade anytime from the customer portal. Downgrades take
          effect at the end of the current billing period.
        </p>
      </div>
    </div>
  );
}
