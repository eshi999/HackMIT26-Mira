import type { ReactNode } from "react";

import { Sidebar } from "@/components/shell/sidebar";
import { TopBar } from "@/components/shell/top-bar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-panel focus:px-3 focus:py-2 focus:text-sm focus:text-ivory"
      >
        Skip to content
      </a>
      <div className="hidden shrink-0 lg:block">
        <Sidebar />
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <TopBar />
        <main id="main-content" className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[1100px] px-6 py-8 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
