import type { ProfileData } from "@/lib/twelvedata"

type Props = { profile: ProfileData }

export function ProfileBlock({ profile }: Props) {
  const { description } = profile
  if (!description) return null

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">About</h2>
      <p className="mt-2 line-clamp-4 text-sm text-zinc-600">
        {description}
      </p>
    </div>
  )
}
