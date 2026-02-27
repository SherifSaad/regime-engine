import { riApi } from "./api"

export type LandingData = Awaited<ReturnType<typeof fetchLandingData>>

export async function fetchLandingData() {
  try {
    const [stats] = await Promise.all([riApi.stats()])
    return { stats }
  } catch {
    return { stats: null }
  }
}

export function formatBars(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M+`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K+`
  return new Intl.NumberFormat().format(n)
}

export function formatInt(n: number): string {
  return new Intl.NumberFormat().format(n)
}
