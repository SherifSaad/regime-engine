import Link from "next/link"

export function Footer() {
  return (
    <footer className="border-t border-zinc-200 py-10">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <p className="mb-4 text-xs text-zinc-500">
          Not investment advice. Not directional forecasts.{" "}
          <Link href="/disclaimer" className="underline hover:text-zinc-700">
            Disclaimer
          </Link>
        </p>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-zinc-500">
            © {new Date().getFullYear()} Regime Intelligence
          </div>
          <div className="flex flex-wrap gap-6 text-sm">
          <Link href="/faq" className="text-zinc-500 hover:text-zinc-900">
            FAQ
          </Link>
          <Link href="/terms" className="text-zinc-500 hover:text-zinc-900">
            Terms
          </Link>
          <Link href="/disclaimer" className="text-zinc-500 hover:text-zinc-900">
            Disclaimer
          </Link>
          <Link href="/privacy" className="text-zinc-500 hover:text-zinc-900">
            Privacy
          </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
