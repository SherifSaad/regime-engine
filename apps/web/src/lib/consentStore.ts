import fs from "node:fs";
import path from "node:path";

export type CookieCategories = {
  necessary: true;        // always true
  analytics: boolean;
  marketing: boolean;
};

export type CookieConsentRecord = {
  anon_id: string;
  user_id?: string | null;
  region: "CA-QC" | "CA" | "UNKNOWN";
  categories: CookieCategories;
  source: "banner_accept_all" | "banner_reject_all" | "modal_save";
  accepted_at: string; // ISO
  ip?: string | null;  // optional (we won't log by default)
};

// Next.js runs with cwd = apps/web, so var/consents is under app root
const CONSENTS_DIR = path.join(process.cwd(), "var", "consents");
const COOKIE_FILE = path.join(CONSENTS_DIR, "cookie_consents.ndjson");

/**
 * Minimal persistence: append-only NDJSON file.
 * - No extra deps
 * - Works on serverless/node runtimes
 * - Later we can swap to SQLite/Postgres without changing client contract
 */
export function appendCookieConsent(rec: CookieConsentRecord) {
  fs.mkdirSync(CONSENTS_DIR, { recursive: true });
  fs.appendFileSync(COOKIE_FILE, JSON.stringify(rec) + "\n", { encoding: "utf8" });
}
