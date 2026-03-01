import { NextResponse } from "next/server";
import { appendCookieConsent, CookieConsentRecord } from "@/lib/consentStore";

export const runtime = "nodejs";

function bad(msg: string, code = 400) {
  return NextResponse.json({ ok: false, error: msg }, { status: code });
}

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return bad("Invalid JSON body.");
  }

  const anon_id = String(body?.anon_id || "");
  const region = (body?.region || "UNKNOWN") as CookieConsentRecord["region"];
  const source = (body?.source || "modal_save") as CookieConsentRecord["source"];
  const categories = body?.categories as Record<string, boolean> | undefined;

  if (!anon_id || anon_id.length < 8) return bad("anon_id missing/invalid.");
  if (!["CA-QC", "CA", "UNKNOWN"].includes(region)) return bad("region invalid.");
  if (!["banner_accept_all", "banner_reject_all", "modal_save"].includes(source)) return bad("source invalid.");

  const normalized = {
    necessary: true as const,
    analytics: Boolean(categories?.analytics),
    marketing: Boolean(categories?.marketing),
  };

  // Quebec-safe: never allow marketing/analytics without explicit consent stored here.
  const rec: CookieConsentRecord = {
    anon_id,
    user_id: (body?.user_id as string | null) ?? null,
    region,
    categories: normalized,
    source,
    accepted_at: new Date().toISOString(),
    ip: null,
  };

  try {
    appendCookieConsent(rec);
  } catch {
    return bad("Failed to persist consent record.", 500);
  }

  return NextResponse.json({ ok: true });
}
