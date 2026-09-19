import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] uppercase tracking-[0.14em]",
  {
    variants: {
      variant: {
        default: "border-brass/40 text-brass",
        ledger: "border-ledger/40 text-ledger",
        alert: "border-alert/40 text-alert",
        mute: "border-line text-mute",
        sandbox: "border-brass/50 bg-brass/10 text-brass",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
