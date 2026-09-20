"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { APP_NAV, isActivePath, routeForPath } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function TopBar() {
  const pathname = usePathname();
  const route = routeForPath(pathname);

  return (
    <header className="border-b border-line bg-ink">
      <div className="mx-auto flex w-full max-w-[1100px] items-start justify-between gap-6 px-6 py-5 lg:px-8">
        <div className="min-w-0">
          <h1 className="font-serif text-2xl tracking-tight text-ivory">{route.title}</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-mute">{route.description}</p>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <p className="text-xs text-ledger">On duty</p>
          <p className="mt-0.5 font-mono text-xs tabular-nums text-mute">19 Sep 2026 · Q3</p>
        </div>
      </div>

      <nav
        className="mx-auto flex w-full max-w-[1100px] gap-1 overflow-x-auto border-t border-line px-3 py-2 [scrollbar-width:none] lg:hidden [&::-webkit-scrollbar]:hidden"
        aria-label="Primary"
      >
        {APP_NAV.map((item) => {
          const active = isActivePath(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60",
                active ? "bg-white/[0.05] text-ivory" : "text-mute hover:text-ivory",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
