"use client"

import Link from "next/link"
import {
  House,
  ChartLine,
  Database,
  ChartBar,
  Question,
  CaretUp,
} from "@phosphor-icons/react"

const SIDEBAR_LINKS = [
  { href: "/", label: "Home", Icon: House },
  { href: "/app", label: "Assets", Icon: Database },
  { href: "/dashboard", label: "My Dashboard", Icon: ChartLine },
  { href: "/app", label: "Statistics", Icon: ChartBar },
  { href: "/faq", label: "FAQ", Icon: Question },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-100">
      <aside className="fixed left-0 top-0 z-40 flex min-h-screen w-56 flex-col bg-[#0d4f3c] p-5">
        <Link href="/" className="block p-2">
          <img src="/Logo_RI_Green_noback.png" alt="Regime Intelligence" className="h-16 w-16 object-contain" />
        </Link>
        <nav className="mt-6">
          {SIDEBAR_LINKS.map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="mb-1 flex items-center gap-3 rounded-lg px-4 py-3 text-white/90 hover:bg-white/10 hover:text-white"
            >
              <link.Icon size={22} weight="regular" />
              <span className="text-sm font-medium">{link.label}</span>
            </Link>
          ))}
        </nav>
        <button
          type="button"
          className="mt-auto flex items-center gap-3 rounded-lg px-4 py-3 text-white/70 hover:text-white"
          aria-label="Collapse"
        >
          <CaretUp size={22} weight="regular" />
          <span className="text-sm">Collapse</span>
        </button>
      </aside>

      <div className="ml-56 flex-1">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-end border-b border-zinc-200 bg-white px-8">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-zinc-600 hover:text-zinc-900">
              Dashboard
            </Link>
            <Link href="/login" className="text-zinc-600 hover:text-zinc-900">
              Log in
            </Link>
            <Link
              href="/signup"
              className="rounded bg-[#22c55e] px-4 py-2 text-sm font-medium text-white hover:bg-[#1ea34e]"
            >
              Sign up free
            </Link>
          </div>
        </header>

        <main className="p-8 pt-10">{children}</main>
      </div>
    </div>
  )
}
