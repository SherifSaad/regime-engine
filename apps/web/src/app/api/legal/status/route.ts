import { NextResponse } from "next/server";
import { getLatestAcceptanceForUser } from "@/lib/legalStore";
import { LEGAL_VERSIONS } from "@/app/legal/_legalMeta";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const user_id = String(searchParams.get("user_id") || "");
  if (!user_id) return NextResponse.json({ ok: false, error: "user_id required" }, { status: 400 });

  const latest = getLatestAcceptanceForUser(user_id);

  return NextResponse.json({
    ok: true,
    current: {
      terms: LEGAL_VERSIONS.terms,
      privacy: LEGAL_VERSIONS.privacy,
      cookies: LEGAL_VERSIONS.cookies,
      disclaimer: LEGAL_VERSIONS.disclaimer,
      subscriptionTerms: LEGAL_VERSIONS.subscriptionTerms,
    },
    accepted: latest,
  });
}
