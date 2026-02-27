"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const NAV_LINKS = [
  { href: "#core", label: "Core" },
  { href: "#earnings", label: "Earnings" },
  { href: "#validation", label: "Validation" },
  { href: "#how-it-works", label: "How it Works" },
  { href: "/faq", label: "FAQ" },
]

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-zinc-200/80 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="text-lg font-semibold tracking-tight text-zinc-900">
          Regime Intelligence
        </Link>

        <nav className="flex items-center gap-4 overflow-x-auto md:gap-6">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm font-medium text-zinc-600 transition-colors hover:text-zinc-900"
              )}
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/explore">Explore</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/login">Log in</Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/signup">Sign up</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/app">Open App</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
