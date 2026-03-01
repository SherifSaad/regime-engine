import { redirect } from "next/navigation"

export default async function AssetClassRedirectPage({
  params,
}: {
  params: Promise<{ assetClass: string }>
}) {
  const { assetClass } = await params
  const decoded = decodeURIComponent(assetClass)
  redirect("/markets")
}
