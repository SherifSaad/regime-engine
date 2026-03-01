import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const runtime = "nodejs";

const CONSENTS_DIR = path.join(process.cwd(), "var", "consents");

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

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const user_id = String(searchParams.get("user_id") || "");
  if (!user_id) return NextResponse.json({ ok: false, error: "user_id required" }, { status: 400 });

  const file = path.join(CONSENTS_DIR, "email_consents.ndjson");
  const rows = readNdjson(file).filter((r) => (r.user_id ?? null) === user_id);

  rows.sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)));
  const latest = rows.length ? rows[rows.length - 1] : null;

  return NextResponse.json({
    ok: true,
    latest: latest
      ? { status: latest.status, timestamp: latest.timestamp, source: latest.source }
      : null,
  });
}
