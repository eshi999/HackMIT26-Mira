import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-line px-5 py-8 text-sm leading-6 text-mute">{children}</p>
  );
}
