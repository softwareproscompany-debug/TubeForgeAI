import Link from "next/link";

export default function KpiCard({
  label,
  value,
  href,
  delta,
}: {
  label: string;
  value: string;
  href: string;
  delta?: string;
}) {
  return (
    <Link
      href={href}
      className="block bg-studio-panel border border-studio-border rounded-lg p-4 hover:border-accent/50 transition-colors"
    >
      <div className="text-xs uppercase tracking-wider text-studio-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-studio-text">{value}</div>
      {delta && <div className="mt-1 text-xs text-studio-faint">{delta}</div>}
    </Link>
  );
}
