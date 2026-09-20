import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

const serif = Newsreader({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mira — Office of the CFO",
  description:
    "Mira is Northstar Labs' digital CFO. One employee. An internal finance organization underneath. Not a chatbot.",
};

const NAV = [
  { href: "/", label: "Command" },
  { href: "/office", label: "Office" },
  { href: "/decisions", label: "Review" },
  { href: "/evidence", label: "Evidence" },
  { href: "/signals", label: "Signals" },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${serif.variable} ${sans.variable} ${mono.variable} font-sans antialiased`}>
        <div className="mx-auto min-h-screen max-w-7xl px-6 pb-16">
          <header className="flex items-center justify-between py-6">
            <Link href="/" className="group flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full border border-brass/50 font-serif text-lg text-brass">
                M
              </span>
              <span>
                <span className="block font-serif text-xl tracking-tight text-ivory">Mira</span>
                <span className="block text-[11px] uppercase tracking-[0.22em] text-mute">
                  Digital CFO · Northstar Labs
                </span>
              </span>
            </Link>
            <nav className="flex items-center gap-1 rounded-full border border-line bg-paper/70 p-1">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-full px-4 py-2 text-xs uppercase tracking-[0.16em] text-mute hover:bg-white/5 hover:text-ivory"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="hidden text-right sm:block">
              <div className="text-[11px] uppercase tracking-[0.18em] text-ledger">On duty</div>
              <div className="font-mono text-xs text-mute">19 Sep 2026 · Q3</div>
            </div>
          </header>
          <div className="hairline mb-8" />
          {children}
        </div>
      </body>
    </html>
  );
}
