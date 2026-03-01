import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const runtime = "nodejs";

const CONSENTS_DIR = path.join(process.cwd(), "var", "consents");
const DELETION_FILE = path.join(CONSENTS_DIR, "deletion_requests.ndjson");

/**
 * Minimal delete:
 * - writes a deletion request record (append-only)
 * - DOES NOT actually delete data yet (no real user DB wired here)
 *
 * Compliance: you can prove user requested deletion; implement actual deletion worker when auth/db exists.
 */
function appendDeletionRequest(rec: {
  user_id: string;
  requested_at: string;
  status: string;
  note: string;
}) {
  fs.mkdirSync(CONSENTS_DIR, { recursive: true });
  fs.appendFileSync(DELETION_FILE, JSON.stringify(rec) + "\n", { encoding: "utf8" });
}

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const user_id = String(body?.user_id || "");
  const confirm = String(body?.confirm || "");

  if (!user_id) return NextResponse.json({ ok: false, error: "user_id required" }, { status: 400 });
  if (confirm !== "DELETE") {
    return NextResponse.json({ ok: false, error: "confirm must equal 'DELETE'" }, { status: 400 });
  }

  const rec = {
    user_id,
    requested_at: new Date().toISOString(),
    status: "requested",
    note:
      "Deletion requested. Some records may be retained where required for legal/security (e.g., billing records, fraud prevention, audit logs).",
  };

  try {
    appendDeletionRequest(rec);
  } catch {
    return NextResponse.json({ ok: false, error: "Failed to persist deletion request." }, { status: 500 });
  }

  return NextResponse.json({ ok: true, status: "requested" });
}
