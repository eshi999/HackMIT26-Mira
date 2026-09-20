"use client";

import { FileSearch, Flag, LayoutDashboard, ListChecks, Radio, Workflow } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";

import { APP_NAV, isActivePath } from "@/lib/nav";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  "/": LayoutDashboard,
  "/findings": Flag,
  "/evidence": FileSearch,
  "/decisions": ListChecks,
  "/office": Workflow,
  "/signals": Radio,
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-dvh w-60 shrink-0 flex-col border-r border-line bg-paper">
      <div className="shrink-0 px-5 py-6">
        <Link
          href="/"
          className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-brass/35 font-serif text-[15px] text-brass">
            M
          </span>
          <span className="min-w-0">
            <span className="block font-serif text-[22px] leading-none tracking-tight text-ivory">Mira</span>
            <span className="mt-1 block text-xs text-mute">Office of the CFO</span>
          </span>
        </Link>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3" aria-label="Primary">
        <ul className="space-y-0.5">
          {APP_NAV.map((item) => {
            const Icon = ICONS[item.href];
            const active = isActivePath(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-sm transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
                    active
                      ? "border-brass bg-white/[0.05] text-ivory"
                      : "border-transparent text-mute hover:bg-white/[0.03] hover:text-ivory",
                  )}
                >
                  {Icon ? <Icon className="h-4 w-4 shrink-0" strokeWidth={1.6} aria-hidden="true" /> : null}
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="shrink-0 border-t border-line px-5 py-4">
        <p className="text-xs text-mute">Workspace</p>
        <p className="mt-1 truncate text-sm text-ivory">Northstar Labs</p>
      </div>
    </aside>
  );
}
