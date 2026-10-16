// Shared bits for the public auth pages — card shell, labeled inputs,
// error/success banners, and the studio-theme class strings.

import type { InputHTMLAttributes, ReactNode } from "react";

export const fieldCls =
  "mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2.5 text-base text-studio-text placeholder:text-studio-faint focus:outline-none focus:border-accent/70 focus:ring-1 focus:ring-accent/40";

export const primaryBtnCls =
  "w-full min-h-[48px] flex items-center justify-center bg-accent text-black font-semibold px-4 py-2.5 rounded-md hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition touch-manipulation";

export const ghostBtnCls =
  "w-full min-h-[48px] flex items-center justify-center border border-studio-border text-studio-text px-4 py-2.5 rounded-md hover:border-accent/60 disabled:opacity-50 disabled:cursor-not-allowed transition touch-manipulation";

export function AuthCard({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Replaces the default max-w-sm (e.g. "max-w-lg" for wider wizards). */
  className?: string;
}) {
  return (
    <div className={`w-full min-w-0 mx-auto ${className ?? "max-w-sm"}`}>
      <div className="bg-studio-panel border border-studio-border rounded-xl p-6 shadow-2xl">
        <div className="mb-6 text-center">
          <div className="text-2xl font-bold tracking-tight text-studio-text">
            TubeForge <span className="text-accent">AI</span>
          </div>
          <h1 className="mt-3 text-lg font-semibold text-studio-text">{title}</h1>
          {subtitle ? (
            <p className="mt-1 text-sm text-studio-muted">{subtitle}</p>
          ) : null}
        </div>
        {children}
      </div>
    </div>
  );
}

export function TextField({
  label,
  id,
  ...rest
}: { label: string; id: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label htmlFor={id} className="block">
      <span className="text-studio-muted text-xs font-medium">{label}</span>
      <input
        id={id}
        {...rest}
        className={rest.className ? `${fieldCls} ${rest.className}` : fieldCls}
      />
    </label>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="text-sm text-red-300 bg-red-500/10 border border-red-500/40 rounded-md p-3"
    >
      {message}
    </div>
  );
}

export function FormSuccess({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="status"
      className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/40 rounded-md p-3"
    >
      {message}
    </div>
  );
}

export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}
