import { NextResponse } from "next/server";
import { appendLegalAcceptance, LegalDoc, LegalAcceptanceRecord } from "@/lib/legalStore";
import { LEGAL_VERSIONS } from "@/app/legal/_legalMeta";

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

  const user_id = String(body?.user_id || "");
  const doc = String(body?.doc || "") as LegalDoc;
  const region = (body?.region || "UNKNOWN") as LegalAcceptanceRecord["region"];
  const source = (body?.source || "signup") as LegalAcceptanceRecord["source"];
  const version = String(body?.version || "");

  if (!user_id) return bad("user_id missing.");
  if (!["terms", "privacy", "cookies", "disclaimer", "subscriptionTerms"].includes(doc)) return bad("doc invalid.");
  if (!["CA-QC", "CA", "UNKNOWN"].includes(region)) return bad("region invalid.");
  if (!["signup", "checkout", "settings"].includes(source)) return bad("source invalid.");

  const current: string =
    doc === "terms" ? LEGAL_VERSIONS.terms :
    doc === "privacy" ? LEGAL_VERSIONS.privacy :
    doc === "cookies" ? LEGAL_VERSIONS.cookies :
    doc === "disclaimer" ? LEGAL_VERSIONS.disclaimer :
    LEGAL_VERSIONS.subscriptionTerms;

  if (version !== current) return bad(`version mismatch. expected ${current}`);

  const rec: LegalAcceptanceRecord = {
    user_id,
    doc,
    version,
    accepted_at: new Date().toISOString(),
    region,
    source,
    ip: null,
  };

  try {
    appendLegalAcceptance(rec);
  } catch {
    return bad("Failed to persist legal acceptance.", 500);
  }

  return NextResponse.json({ ok: true });
}
