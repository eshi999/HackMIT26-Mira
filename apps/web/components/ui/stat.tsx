import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Stat({
  label,
  value,
  hint,
  className,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-xs text-mute">{label}</div>
      <div
        className={cn(
          "mt-1 font-serif text-3xl tabular-nums tracking-tight text-ivory",
          valueClassName,
        )}
      >
        {value}
      </div>
      {hint ? <div className="mt-1 text-xs text-mute">{hint}</div> : null}
    </div>
  );
}
