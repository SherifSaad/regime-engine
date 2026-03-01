"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  ChartPieSlice,
  Database,
  Bell,
  MapTrifold,
  FileText,
  CaretUp,
  User,
  ShieldCheck,
  EnvelopeSimple,
  ClipboardText,
} from "@phosphor-icons/react"

const SIDEBAR_LINKS = [
  { href: "/overview", label: "Global Overview", Icon: ChartPieSlice },
  { href: "/markets", label: "Markets", Icon: Database },
  { href: "/alerts", label: "Alerts Center", Icon: Bell },
  { href: "/market-map", label: "Market Map", Icon: MapTrifold },
  { href: "/audit", label: "Audit", Icon: FileText },
  { href: "/settings/profile", label: "Profile", Icon: User },
  { href: "/settings/legal", label: "Legal & Consents", Icon: ClipboardText },
  { href: "/settings/privacy", label: "Privacy", Icon: ShieldCheck },
  { href: "/settings/communications", label: "Communications", Icon: EnvelopeSimple },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  return (
    <div className="flex min-h-screen bg-zinc-100">
      <aside className="fixed left-0 top-0 z-40 flex min-h-screen w-56 flex-col rounded-r-2xl bg-[#0d4f3c] p-5 shadow-lg">
        <Link href="/" className="flex justify-center p-2">
          <img src="/Logo_RI_Green_noback.png" alt="Regime Intelligence" className="h-48 w-48 object-contain" />
        </Link>
        <nav className="mt-6">
          {SIDEBAR_LINKS.map((link) => {
            const isActive = pathname.startsWith(link.href)
            return (
            <Link
              key={link.label}
              href={link.href}
              className={`mb-1 flex items-center gap-3 rounded-lg px-4 py-3 ${isActive ? "bg-[#22c55e] text-white" : "text-white/90 hover:bg-white/10 hover:text-white"}`}
            >
              <link.Icon size={22} weight="regular" />
              <span className="text-sm font-medium">{link.label}</span>
            </Link>
          )})}
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
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-8">
          <h1 className="text-lg font-semibold text-zinc-900">Regime Intelligence</h1>
          <nav className="flex items-center gap-6 text-sm">
            <Link href="/" className="text-zinc-600 hover:text-zinc-900">
              Home
            </Link>
            <Link href="/markets" className="text-zinc-600 hover:text-zinc-900">
              Markets
            </Link>
          </nav>
        </header>

        <main className="p-8 pt-10">{children}</main>
      </div>
    </div>
  )
}
