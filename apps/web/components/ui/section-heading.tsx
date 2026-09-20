import Link from "next/link";

export function SectionHeading({
  title,
  meta,
  href,
  linkLabel,
}: {
  title: string;
  meta?: string;
  href?: string;
  linkLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 className="font-serif text-xl text-ivory">{title}</h2>
        {meta ? <p className="mt-1 text-xs text-mute">{meta}</p> : null}
      </div>
      {href && linkLabel ? (
        <Link
          href={href}
          className="text-sm text-brass transition-colors hover:text-ivory focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60"
        >
          {linkLabel}
        </Link>
      ) : null}
    </div>
  );
}
