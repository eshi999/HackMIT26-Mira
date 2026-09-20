import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function ListPanel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("divide-y divide-line overflow-hidden rounded-lg border border-line", className)}
      {...props}
    />
  );
}

export const listRowClassName = "px-5 py-4 transition-colors hover:bg-white/[0.02]";

export const listRowInteractiveClassName = cn(
  listRowClassName,
  "block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-inset",
);
