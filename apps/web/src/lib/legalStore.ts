import fs from "node:fs";
import path from "node:path";

export type LegalDoc = "terms" | "privacy" | "cookies" | "disclaimer" | "subscriptionTerms";

export type LegalAcceptanceRecord = {
  user_id: string;
  doc: LegalDoc;
  version: string;
  accepted_at: string; // ISO
  region: "CA-QC" | "CA" | "UNKNOWN";
  source: "signup" | "checkout" | "settings";
  ip?: string | null; // optional (we won't log by default)
};

export type EmailConsentRecord = {
  user_id?: string | null;
  email?: string | null;
  type: "product_updates";
  status: "opt_in" | "opt_out";
  source: "signup" | "settings" | "unsubscribe_link";
  timestamp: string; // ISO
  region: "CA-QC" | "CA" | "UNKNOWN";
};

// Next.js runs with cwd = apps/web, so var/consents is under app root
const CONSENTS_DIR = path.join(process.cwd(), "var", "consents");
const LEGAL_FILE = path.join(CONSENTS_DIR, "user_legal_acceptance.ndjson");
const EMAIL_FILE = path.join(CONSENTS_DIR, "email_consents.ndjson");

function ensureDir() {
  fs.mkdirSync(CONSENTS_DIR, { recursive: true });
}

export function appendLegalAcceptance(rec: LegalAcceptanceRecord) {
  ensureDir();
  fs.appendFileSync(LEGAL_FILE, JSON.stringify(rec) + "\n", { encoding: "utf8" });
}

export function appendEmailConsent(rec: EmailConsentRecord) {
  ensureDir();
  fs.appendFileSync(EMAIL_FILE, JSON.stringify(rec) + "\n", { encoding: "utf8" });
}

/**
 * Minimal read helpers (NDJSON scan).
 * For small scale this is fine. Swap to DB later.
 */
export function getLatestAcceptanceForUser(user_id: string): Record<string, { version: string; accepted_at: string }> {
  if (!fs.existsSync(LEGAL_FILE)) return {};
  const lines = fs.readFileSync(LEGAL_FILE, "utf8").trim().split("\n").filter(Boolean);
  const latest: Record<string, { version: string; accepted_at: string }> = {};
  for (const ln of lines) {
    try {
      const r = JSON.parse(ln) as LegalAcceptanceRecord;
      if (r.user_id !== user_id) continue;
      latest[r.doc] = { version: r.version, accepted_at: r.accepted_at };
    } catch {
      // skip malformed lines
    }
  }
  return latest;
}
