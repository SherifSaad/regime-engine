import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const runtime = "nodejs";

const CONSENTS_DIR = path.join(process.cwd(), "var", "consents");

/**
 * Minimal export:
 * - reads append-only NDJSON consent logs
 * - returns a single JSON file download
 *
 * Later: add saved screens, account profile, billing metadata, etc.
 */
function readNdjson(filePath: string): Record<string, unknown>[] {
  if (!fs.existsSync(filePath)) return [];
  const txt = fs.readFileSync(filePath, "utf8").trim();
  if (!txt) return [];
  return txt.split("\n").map((ln) => {
    try {
      return JSON.parse(ln) as Record<string, unknown>;
    } catch {
      return null;
    }
  }).filter((x): x is Record<string, unknown> => x != null);
}

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const user_id = String(body?.user_id || "");
  if (!user_id) return NextResponse.json({ ok: false, error: "user_id required" }, { status: 400 });

  const legal = readNdjson(path.join(CONSENTS_DIR, "user_legal_acceptance.ndjson")).filter(
    (r) => r.user_id === user_id
  );
  const email = readNdjson(path.join(CONSENTS_DIR, "email_consents.ndjson")).filter(
    (r) => (r.user_id ?? null) === user_id
  );
  const cookies = readNdjson(path.join(CONSENTS_DIR, "cookie_consents.ndjson")).filter(
    (r) => (r.user_id ?? null) === user_id
  );

  const exportObj = {
    exported_at: new Date().toISOString(),
    user_id,
    data: {
      legal_acceptance: legal,
      email_consents: email,
      cookie_consents: cookies,
    },
    notes: [
      "This export includes consent and legal acceptance records currently stored by the Service.",
      "Additional account data and saved screens will appear here once persistence is wired.",
    ],
  };

  const json = JSON.stringify(exportObj, null, 2);
  const filename = `regime-intelligence-export_${user_id}_${Date.now()}.json`;

  return new NextResponse(json, {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
