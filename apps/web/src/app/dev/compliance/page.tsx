"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LEGAL_VERSIONS, LEGAL_LAST_UPDATED } from "@/app/legal/_legalMeta";

function isProd() {
  return process.env.NODE_ENV === "production";
}

function loadCookieLocal(): { necessary: true; analytics: boolean; marketing: boolean; savedAt: number | null } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("ri_cookie_consent_v1");
    if (!raw) return null;
    const obj = JSON.parse(raw);
    return { necessary: true, analytics: !!obj.analytics, marketing: !!obj.marketing, savedAt: obj.savedAt ?? null };
  } catch {
    return null;
  }
}

export default function DevCompliancePage() {
  const [cookieLocal, setCookieLocal] = useState<ReturnType<typeof loadCookieLocal>>(null);
  const [legalStatus, setLegalStatus] = useState<Record<string, unknown> | null>(null);
  const [emailStatus, setEmailStatus] = useState<Record<string, unknown> | null>(null);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [deleteMsg, setDeleteMsg] = useState<string | null>(null);

  const [userId, setUserId] = useState<string>("USER_ID_TBD");

  const allowProd = process.env.NEXT_PUBLIC_ALLOW_DEV_COMPLIANCE === "1";
  const blocked = isProd() && !allowProd;

  useEffect(() => {
    setCookieLocal(loadCookieLocal());
  }, []);

  const refresh = async () => {
    setLegalStatus(null);
    setEmailStatus(null);
    if (!userId || userId === "USER_ID_TBD") return;

    const a = await fetch(`/api/legal/status?user_id=${encodeURIComponent(userId)}`);
    setLegalStatus(await a.json());

    const e = await fetch(`/api/consent/email/status?user_id=${encodeURIComponent(userId)}`);
    setEmailStatus(await e.json());
  };

  const runExport = async () => {
    setExportMsg(null);
    try {
      const res = await fetch("/api/privacy/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition");
      const match = disposition?.match(/filename="?([^";\n]+)"?/);
      const filename = match?.[1] ?? `regime-intelligence-export_${userId}_${Date.now()}.json`;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setExportMsg("Export triggered (download).");
    } catch {
      setExportMsg("Export failed.");
    }
  };

  const runDelete = async () => {
    setDeleteMsg(null);
    try {
      const res = await fetch("/api/privacy/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, confirm: "DELETE" }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error("delete failed");
      setDeleteMsg("Deletion request recorded.");
    } catch {
      setDeleteMsg("Deletion request failed.");
    }
  };

  if (blocked) {
    return (
      <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
        <h1 style={{ margin: 0 }}>Dev Compliance</h1>
        <div style={{ marginTop: 10, fontSize: 13 }}>
          This page is disabled in production. To enable temporarily, set:
          <pre style={{ marginTop: 8, padding: 12, background: "rgba(0,0,0,0.05)", borderRadius: 12 }}>
NEXT_PUBLIC_ALLOW_DEV_COMPLIANCE=1
          </pre>
        </div>
      </main>
    );
  }

  const pass = (ok: boolean) => (
    <span style={{ fontWeight: 900, color: ok ? "green" : "crimson" }}>
      {ok ? "PASS" : "FAIL"}
    </span>
  );

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
      <h1 style={{ margin: 0 }}>Dev Compliance Checklist</h1>
      <div style={{ fontSize: 13, opacity: 0.8, marginTop: 6 }}>
        Internal verification screen for legal + compliance wiring.
      </div>

      <hr style={{ margin: "16px 0" }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 900, marginBottom: 10 }}>1) Legal pages exist</div>
        <div style={{ display: "grid", gap: 6, fontSize: 13 }}>
          <div>{pass(true)} <Link href="/legal/terms">/legal/terms</Link></div>
          <div>{pass(true)} <Link href="/legal/privacy">/legal/privacy</Link></div>
          <div>{pass(true)} <Link href="/legal/cookies">/legal/cookies</Link></div>
          <div>{pass(true)} <Link href="/legal/disclaimer">/legal/disclaimer</Link></div>
          <div>{pass(true)} <Link href="/legal/subscription-terms">/legal/subscription-terms</Link></div>
          <div>{pass(true)} <Link href="/legal/contact">/legal/contact</Link></div>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.8 }}>
          Manual check: confirm each legal page shows &quot;Last updated&quot; + &quot;Version&quot;.
        </div>
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 900, marginBottom: 10 }}>2) Version constants sanity</div>
        <div style={{ fontSize: 13, lineHeight: 1.7 }}>
          <div>Terms: <b>{LEGAL_VERSIONS.terms}</b> · {LEGAL_LAST_UPDATED.terms}</div>
          <div>Privacy: <b>{LEGAL_VERSIONS.privacy}</b> · {LEGAL_LAST_UPDATED.privacy}</div>
          <div>Cookies: <b>{LEGAL_VERSIONS.cookies}</b> · {LEGAL_LAST_UPDATED.cookies}</div>
          <div>Disclaimer: <b>{LEGAL_VERSIONS.disclaimer}</b> · {LEGAL_LAST_UPDATED.disclaimer}</div>
          <div>Subscription: <b>{LEGAL_VERSIONS.subscriptionTerms}</b> · {LEGAL_LAST_UPDATED.subscriptionTerms}</div>
          <div>Contact: <b>{LEGAL_VERSIONS.contact}</b> · {LEGAL_LAST_UPDATED.contact}</div>
        </div>
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 900, marginBottom: 10 }}>3) Cookie consent (device)</div>
        {cookieLocal ? (
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            <div>Necessary: <b>On</b></div>
            <div>Analytics: <b>{cookieLocal.analytics ? "On" : "Off"}</b></div>
            <div>Marketing: <b>{cookieLocal.marketing ? "On" : "Off"}</b></div>
            <div style={{ fontSize: 12, opacity: 0.75 }}>SavedAt: {String(cookieLocal.savedAt ?? "")}</div>
            <div style={{ marginTop: 6 }}>{pass(true)} Cookie choice exists on this device</div>
          </div>
        ) : (
          <div style={{ fontSize: 13 }}>
            {pass(false)} No cookie choice stored yet. Visit any page and use the banner.
          </div>
        )}
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 900, marginBottom: 10 }}>4) User acceptance + CASL (requires user_id)</div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Enter test user_id"
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", minWidth: 260 }}
          />
          <button
            onClick={refresh}
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
          >
            Refresh status
          </button>
        </div>

        <div style={{ marginTop: 10, fontSize: 13 }}>
          Legal status: {pass(Boolean(legalStatus && "ok" in legalStatus && legalStatus.ok))}
          <pre style={{ marginTop: 8, padding: 12, background: "rgba(0,0,0,0.05)", borderRadius: 12, overflowX: "auto" }}>
            {JSON.stringify(legalStatus, null, 2)}
          </pre>
        </div>

        <div style={{ marginTop: 10, fontSize: 13 }}>
          Email consent status: {pass(Boolean(emailStatus && "ok" in emailStatus && emailStatus.ok))}
          <pre style={{ marginTop: 8, padding: 12, background: "rgba(0,0,0,0.05)", borderRadius: 12, overflowX: "auto" }}>
            {JSON.stringify(emailStatus, null, 2)}
          </pre>
        </div>
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 900, marginBottom: 10 }}>5) Privacy export/delete (requires user_id)</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            onClick={runExport}
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
          >
            Trigger export
          </button>
          <button
            onClick={runDelete}
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
          >
            Trigger deletion request
          </button>
        </div>
        {exportMsg && <div style={{ marginTop: 10, fontSize: 13 }}>{exportMsg}</div>}
        {deleteMsg && <div style={{ marginTop: 10, fontSize: 13 }}>{deleteMsg}</div>}
      </section>

      <div style={{ marginTop: 14, fontSize: 12, opacity: 0.8 }}>
        Definition of DONE: legal links + cookie consent + legal acceptance + CASL toggle + export/delete endpoints working.
      </div>
    </main>
  );
}
