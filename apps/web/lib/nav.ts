export type AppRoute = {
  href: string;
  label: string;
  title: string;
  description: string;
};

export const APP_NAV: AppRoute[] = [
  {
    href: "/",
    label: "Command center",
    title: "Command center",
    description: "Overnight briefing, cash position, and items that still need a human.",
  },
  {
    href: "/findings",
    label: "Findings",
    title: "Findings",
    description: "Exceptions Mira flagged. Open a memo for impact, evidence, and next step.",
  },
  {
    href: "/evidence",
    label: "Evidence",
    title: "Evidence",
    description: "Source documents, lineage, and retrieved hits.",
  },
  {
    href: "/decisions",
    label: "Approvals",
    title: "Approvals",
    description: "Human review queue. Approve, reject, or record scoped precedent.",
  },
  {
    href: "/office",
    label: "How it works",
    title: "How it works",
    description: "One AI CFO at the surface. Deterministic finance systems underneath.",
  },
  {
    href: "/signals",
    label: "Signals",
    title: "Signals",
    description: "Public observations. Isolated from finance truth, savings, and decisions.",
  },
];

export function routeForPath(pathname: string): AppRoute {
  const exact = APP_NAV.find((item) => item.href === pathname);
  if (exact) return exact;
  const nested = APP_NAV.find(
    (item) => item.href !== "/" && pathname.startsWith(`${item.href}/`),
  );
  return nested ?? APP_NAV[0];
}

export function isActivePath(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
