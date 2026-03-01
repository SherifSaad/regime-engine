"use client"

import Link from "next/link"

const PUBLIC_LINKS = [
  { href: "/", label: "Home" },
  { href: "/markets", label: "Markets" },
  { href: "/methodology", label: "Methodology" },
  { href: "/audit", label: "Audit" },
  { href: "/pricing", label: "Pricing" },
]

export function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-zinc-200">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="text-lg font-semibold text-zinc-900">
            Regime Intelligence
          </Link>
          <nav className="flex items-center gap-6">
            {PUBLIC_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-zinc-600 hover:text-zinc-900"
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/login"
              className="text-sm text-zinc-600 hover:text-zinc-900"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="rounded bg-[#0d4f3c] px-4 py-2 text-sm font-medium text-white hover:bg-[#165a45]"
            >
              Sign up
            </Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}
