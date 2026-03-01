import { NextResponse } from "next/server";
import { appendEmailConsent, EmailConsentRecord } from "@/lib/legalStore";

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

  const source = (body?.source || "signup") as EmailConsentRecord["source"];
  const region = (body?.region || "UNKNOWN") as EmailConsentRecord["region"];

  if (!["signup", "settings", "unsubscribe_link"].includes(source)) return bad("source invalid.");
  if (!["CA-QC", "CA", "UNKNOWN"].includes(region)) return bad("region invalid.");

  const rec: EmailConsentRecord = {
    user_id: (body?.user_id as string | null) ?? null,
    email: (body?.email as string | null) ?? null,
    type: "product_updates",
    status: body?.status === "opt_out" ? "opt_out" : "opt_in",
    source,
    timestamp: new Date().toISOString(),
    region,
  };

  try {
    appendEmailConsent(rec);
  } catch {
    return bad("Failed to persist email consent.", 500);
  }

  return NextResponse.json({ ok: true });
}
