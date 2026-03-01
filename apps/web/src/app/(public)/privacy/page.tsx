import Link from "next/link"

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
        ← Back
      </Link>
      <h1 className="mt-6 text-3xl font-bold tracking-tight">
        Privacy Policy
      </h1>
      <div className="mt-8 space-y-4 text-zinc-600">
        <p>Privacy policy content. Placeholder.</p>
      </div>
    </div>
  )
}
