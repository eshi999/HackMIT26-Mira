import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-md border px-3 py-1.5 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-offset-2 focus-visible:ring-offset-ink",
        active
          ? "border-brass/40 bg-brass/10 text-ivory"
          : "border-line text-mute hover:border-line hover:text-ivory",
      )}
    >
      {children}
    </button>
  );
}
