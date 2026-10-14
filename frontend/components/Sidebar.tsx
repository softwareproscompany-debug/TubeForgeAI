"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONS: Record<string, JSX.Element> = {
  overview: (
    <path d="M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" strokeLinecap="round" strokeLinejoin="round" />
  ),
  command: (
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3zM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16z" strokeLinejoin="round" />
  ),
  channels: (
    <path d="M10 8l6 4-6 4V8zM4 5h16a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V6a1 1 0 011-1z" strokeLinejoin="round" />
  ),
  research: (
    <path d="M11 4a7 7 0 105.2 11.6L21 20.4" strokeLinecap="round" />
  ),
  calendar: (
    <path d="M4 6h16v14H4zM4 10h16M8 3v5M16 3v5" strokeLinecap="round" strokeLinejoin="round" />
  ),
  projects: (
    <path d="M4 7l8-4 8 4-8 4-8-4zM4 7v10l8 4 8-4V7M12 11v10" strokeLinecap="round" strokeLinejoin="round" />
  ),
  queue: (
    <path d="M4 6h16M4 12h16M4 18h10" strokeLinecap="round" />
  ),
  media: (
    <path d="M4 5h16v14H4zM4 5l7 7 3-3 6 6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  editor: (
    <path d="M4 20l4-1 11-11a2.1 2.1 0 00-3-3L5 16l-1 4zM14 6l3 3" strokeLinecap="round" strokeLinejoin="round" />
  ),
  publishing: (
    <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
  ),
  analytics: (
    <path d="M5 20V10M11 20V4M17 20v-7M3 20h18" strokeLinecap="round" />
  ),
  models: (
    <path d="M12 3v18M5 8l14 8M19 8L5 16" strokeLinecap="round" />
  ),
  automation: (
    <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" strokeLinejoin="round" />
  ),
  health: (
    <path d="M12 21s-7-4.6-9.5-9A5.5 5.5 0 0112 6a5.5 5.5 0 019.5 6c-2.5 4.4-9.5 9-9.5 9z" strokeLinejoin="round" />
  ),
  settings: (
    <path d="M4 8h16M4 16h16M8 4v6M16 12v6" strokeLinecap="round" />
  ),
};

const NAV: { href: string; label: string; icon: string }[] = [
  { href: "/overview", label: "Overview", icon: "overview" },
  { href: "/command-center", label: "AI Command Center", icon: "command" },
  { href: "/channels", label: "Channels", icon: "channels" },
  { href: "/research", label: "Research", icon: "research" },
  { href: "/calendar", label: "Content Calendar", icon: "calendar" },
  { href: "/projects", label: "Projects", icon: "projects" },
  { href: "/queue", label: "Production Queue", icon: "queue" },
  { href: "/media-library", label: "Media Library", icon: "media" },
  { href: "/editor", label: "Video Editor", icon: "editor" },
  { href: "/publishing", label: "Publishing", icon: "publishing" },
  { href: "/analytics", label: "Analytics", icon: "analytics" },
  { href: "/models", label: "AI Models & Providers", icon: "models" },
  { href: "/automation", label: "Automation Workflows", icon: "automation" },
  { href: "/health", label: "System Health", icon: "health" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 w-60 bg-studio-panel border-r border-studio-border flex flex-col">
      <div className="px-5 py-5 border-b border-studio-border">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-accent" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <div className="font-semibold text-studio-text tracking-wide">TubeForge AI</div>
            <div className="text-[11px] text-studio-faint">YouTube OS · Private</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV.map((item) => {
          const active =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-accent/10 text-accent border border-accent/30"
                  : "text-studio-muted hover:text-studio-text hover:bg-studio-panel2 border border-transparent"
              }`}
            >
              <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8}>
                {ICONS[item.icon]}
              </svg>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-studio-border text-[11px] text-studio-faint">
        Local-first AI gateway · no per-generation credits
      </div>
    </aside>
  );
}
