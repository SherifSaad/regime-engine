"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { LEGAL_VERSIONS } from "@/app/legal/_legalMeta";

type Region = "CA-QC" | "CA" | "UNKNOWN";

function inferRegion(): Region {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    const lang = navigator.language || "";
    if (lang.toLowerCase().startsWith("fr-ca") || tz.includes("America/Montreal")) return "CA-QC";
    if (tz.includes("America/Toronto") || tz.includes("America/Vancouver")) return "CA";
    return "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

async function postAccept(payload: {
  user_id: string;
  doc: string;
  version: string;
  region: Region;
  source: string;
}) {
  const res = await fetch("/api/legal/accept", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.json()).error || "Accept failed");
}

async function postEmailConsent(payload: {
  user_id: string;
  email: string | null;
  status: "opt_in" | "opt_out";
  source: string;
  region: Region;
}) {
  await fetch("/api/consent/email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export type LegalAcceptanceBlockRef = {
  record: () => Promise<boolean>;
  agree: boolean;
};

/**
 * Minimal UI block for signup/checkout:
 * - required: accept terms + privacy (links open new tab)
 * - optional: marketing (CASL) opt-in
 *
 * Pass a ref to call record() from parent on form submit. Disable submit until agree is true.
 *
 * IMPORTANT — user_id and real accounts:
 * If you use a temporary id at signup (e.g. "tmp_"+Date.now()) because the user doesn't exist yet,
 * you MUST call the same endpoints again with the real user_id once the account is created:
 * POST /api/legal/accept (terms + privacy) and, if they opted in, POST /api/consent/email.
 * Otherwise acceptance is only stored under the temp id. Prefer passing the real user_id into
 * this component as soon as you have it (e.g. from your auth create-user hook).
 */
const LegalAcceptanceBlock = React.forwardRef<LegalAcceptanceBlockRef, {
  userId: string;
  email?: string | null;
  source: "signup" | "checkout";
  onValidityChange?: (valid: boolean) => void;
}>(function LegalAcceptanceBlockInner(props, ref) {
  const region = useMemo(() => inferRegion(), []);
  const [agree, setAgree] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [busy, setBusy] = useState(false);

  const valid = agree;

  useEffect(() => {
    props.onValidityChange?.(valid);
  }, [valid, props.onValidityChange]);

  const record = useCallback(async () => {
    if (!agree) return false;
    setBusy(true);
    try {
      await postAccept({
        user_id: props.userId,
        doc: "terms",
        version: LEGAL_VERSIONS.terms,
        region,
        source: props.source,
      });
      await postAccept({
        user_id: props.userId,
        doc: "privacy",
        version: LEGAL_VERSIONS.privacy,
        region,
        source: props.source,
      });
      if (marketing) {
        await postEmailConsent({
          user_id: props.userId,
          email: props.email ?? null,
          status: "opt_in",
          source: props.source,
          region,
        });
      }
      return true;
    } catch {
      return false;
    } finally {
      setBusy(false);
    }
  }, [agree, marketing, props.userId, props.email, props.source, region]);

  useImperativeHandle(ref, () => ({ record, agree }), [record, agree]);

  return (
    <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12 }}>
      <label style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <input
          type="checkbox"
          checked={agree}
          onChange={(e) => setAgree(e.target.checked)}
          style={{ marginTop: 4 }}
        />
        <div style={{ fontSize: 13, lineHeight: 1.35 }}>
          <div style={{ fontWeight: 700 }}>
            I agree to the{" "}
            <Link href="/legal/terms" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "underline" }}>
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/legal/privacy" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "underline" }}>
              Privacy Policy
            </Link>
            .
          </div>
          <div style={{ fontSize: 12, opacity: 0.85, marginTop: 4 }}>
            Required to create an account and use the Service.
          </div>
        </div>
      </label>

      <div style={{ height: 10 }} />

      <label style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <input
          type="checkbox"
          checked={marketing}
          onChange={(e) => setMarketing(e.target.checked)}
          style={{ marginTop: 4 }}
        />
        <div style={{ fontSize: 13, lineHeight: 1.35 }}>
          <div style={{ fontWeight: 700 }}>Send me product updates (optional)</div>
          <div style={{ fontSize: 12, opacity: 0.85, marginTop: 4 }}>
            You can turn this off anytime in Settings. We only send marketing emails if you opt in.
          </div>
        </div>
      </label>

        <div style={{ marginTop: 12, fontSize: 12, opacity: 0.8 }}>
          Version: Terms {LEGAL_VERSIONS.terms} · Privacy {LEGAL_VERSIONS.privacy}
        </div>
      </div>
    );
  }
);

export default LegalAcceptanceBlock;
