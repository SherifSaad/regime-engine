import Link from "next/link"

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-zinc-900">My Dashboard</h1>
      <p className="mt-2 text-zinc-600">Add favorite tickers, track watchlists, and more.</p>

      <div className="mt-8 rounded-xl border bg-white p-6">
        <h2 className="font-semibold text-zinc-900">Favorites</h2>
        <p className="mt-2 text-sm text-zinc-500">
          Add tickers to your watchlist. Sign up free to save — no credit card required.
        </p>
        <div className="mt-4 flex gap-2">
          <input
            type="text"
            placeholder="Add ticker (e.g. AAPL)"
            className="rounded border border-zinc-200 px-3 py-2 text-sm"
          />
          <Link
            href="/signup"
            className="rounded bg-[#22c55e] px-4 py-2 text-sm font-medium text-white hover:bg-[#1ea34e]"
          >
            Sign up to save
          </Link>
        </div>
      </div>
    </div>
  )
}
