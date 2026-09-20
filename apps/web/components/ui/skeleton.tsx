import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-white/[0.06]", className)} {...props} />;
}

type PageSkeletonVariant = "page" | "list" | "memo" | "dashboard";

export function PageSkeleton({
  label = "Loading",
  variant = "page",
}: {
  label?: string;
  variant?: PageSkeletonVariant;
}) {
  return (
    <div className="space-y-8" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      {variant === "dashboard" ? <DashboardSkeleton /> : null}
      {variant === "list" ? <ListSkeleton /> : null}
      {variant === "memo" ? <MemoSkeleton /> : null}
      {variant === "page" ? <DefaultSkeleton /> : null}
    </div>
  );
}

function DefaultSkeleton() {
  return (
    <>
      <div className="space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="h-48 w-full" />
    </>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="max-w-3xl space-y-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-8 w-full max-w-xl" />
        <Skeleton className="h-4 w-full max-w-lg" />
      </div>
      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-line lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="border-line p-5 lg:border-r lg:last:border-r-0">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-2 h-8 w-24" />
            <Skeleton className="mt-2 h-3 w-28" />
          </div>
        ))}
      </div>
      <div className="space-y-3">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    </>
  );
}

function ListSkeleton() {
  return (
    <>
      <Skeleton className="h-10 w-full max-w-md" />
      <div className="overflow-hidden rounded-lg border border-line">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="space-y-3 border-b border-line px-5 py-4 last:border-b-0">
            <div className="flex gap-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-20" />
            </div>
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-4 w-full max-w-xl" />
          </div>
        ))}
      </div>
    </>
  );
}

function MemoSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <Skeleton className="h-4 w-24" />
      <div className="flex gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
      </div>
      <Skeleton className="h-9 w-full max-w-lg" />
      <Skeleton className="h-10 w-40" />
      <div className="space-y-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-16 w-full" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-3 w-36" />
        <Skeleton className="h-24 w-full" />
      </div>
    </div>
  );
}
