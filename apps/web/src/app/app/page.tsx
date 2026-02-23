import Link from "next/link";
import { riApi } from "@/lib/api";

export default async function AppHome() {
  const classes = await riApi.assetClasses();

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold">Dashboard</h2>
            <p className="mt-1 text-sm text-zinc-600">
              Select an asset class → then an asset (next step).
            </p>
          </div>
          <Link className="text-sm underline" href="/">Back to landing</Link>
        </div>

        <div className="mt-8 rounded-2xl border p-6">
          <div className="text-sm font-semibold">Asset classes</div>
          <div className="mt-4 flex flex-wrap gap-2">
            {classes.map((c) => (
              <span key={c} className="rounded-full border px-3 py-1 text-sm">
                {c}
              </span>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
