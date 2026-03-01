"use client";

import { useEffect, useMemo, useState } from "react";
import { LEGAL_VERSIONS } from "@/app/legal/_legalMeta";

function fakeUserId() {
  // Replace with real auth session user id later
  return "USER_ID_TBD";
}

type LegalStatusResp = {
  ok: boolean;
  current: Record<string, string>;
  accepted: Record<string, { version: string; accepted_at: string }>;
};

type EmailLatest = { status: string; timestamp: string; source: string } | null;

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

export default function LegalSettingsPage() {
  const userId = useMemo(() => fakeUserId(), []);
  const [legal, setLegal] = useState<LegalStatusResp | null>(null);
  const [emailLatest, setEmailLatest] = useState<EmailLatest>(null);
  const [cookieLocal, setCookieLocal] = useState<ReturnType<typeof loadCookieLocal>>(null);

  useEffect(() => {
    setCookieLocal(loadCookieLocal());
  }, []);

  useEffect(() => {
    if (userId === "USER_ID_TBD") return;

    (async () => {
      const a = await fetch(`/api/legal/status?user_id=${encodeURIComponent(userId)}`);
      const aj = await a.json();
      setLegal(aj);

      const e = await fetch(`/api/consent/email/status?user_id=${encodeURIComponent(userId)}`);
      const ej = await e.json();
      setEmailLatest(ej?.latest ?? null);
    })();
  }, [userId]);

  function acceptedCurrent(doc: "terms" | "privacy" | "cookies" | "disclaimer" | "subscriptionTerms") {
    const current =
      doc === "terms" ? LEGAL_VERSIONS.terms :
      doc === "privacy" ? LEGAL_VERSIONS.privacy :
      doc === "cookies" ? LEGAL_VERSIONS.cookies :
      doc === "disclaimer" ? LEGAL_VERSIONS.disclaimer :
      LEGAL_VERSIONS.subscriptionTerms;

    const a = legal?.accepted?.[doc];
    return a?.version === current ? { ok: true, at: a.accepted_at } : { ok: false, at: a?.accepted_at ?? null };
  }

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
      <h1 style={{ margin: 0 }}>Legal & Consents</h1>
      <div style={{ fontSize: 13, opacity: 0.8, marginTop: 6 }}>
        View the versions you accepted and your consent preferences.
      </div>

      <hr style={{ margin: "16px 0" }} />

      {userId === "USER_ID_TBD" && (
        <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14, fontSize: 13 }}>
          <b>Not fully active yet.</b> This page will show acceptance records once real authentication user_id is wired.
        </div>
      )}

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 800, marginBottom: 10 }}>Current legal versions</div>
        <div style={{ fontSize: 13, lineHeight: 1.6 }}>
          <div>Terms: <b>{LEGAL_VERSIONS.terms}</b></div>
          <div>Privacy: <b>{LEGAL_VERSIONS.privacy}</b></div>
          <div>Cookies: <b>{LEGAL_VERSIONS.cookies}</b></div>
          <div>Disclaimer: <b>{LEGAL_VERSIONS.disclaimer}</b></div>
          <div>Subscription Terms: <b>{LEGAL_VERSIONS.subscriptionTerms}</b></div>
        </div>
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 800, marginBottom: 10 }}>Your acceptance status</div>

        {userId === "USER_ID_TBD" ? (
          <div style={{ fontSize: 13, opacity: 0.85 }}>Connect auth to show acceptance history.</div>
        ) : (
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            {(["terms", "privacy", "cookies", "disclaimer", "subscriptionTerms"] as const).map((d) => {
              const st = acceptedCurrent(d);
              return (
                <div key={d}>
                  {d}: {st.ok ? <b>Accepted</b> : <b>Not accepted</b>}
                  {st.at ? <span style={{ opacity: 0.75 }}> · {st.at}</span> : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 800, marginBottom: 10 }}>Cookie consent (device)</div>
        {cookieLocal ? (
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            <div>Necessary: <b>On</b></div>
            <div>Analytics: <b>{cookieLocal.analytics ? "On" : "Off"}</b></div>
            <div>Marketing: <b>{cookieLocal.marketing ? "On" : "Off"}</b></div>
          </div>
        ) : (
          <div style={{ fontSize: 13, opacity: 0.85 }}>No cookie decision stored on this device yet.</div>
        )}
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
          You can change this via the cookie banner (clear browser storage to re-open immediately).
        </div>
      </section>

      <div style={{ height: 12 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ fontWeight: 800, marginBottom: 10 }}>Marketing emails</div>
        {userId === "USER_ID_TBD" ? (
          <div style={{ fontSize: 13, opacity: 0.85 }}>Connect auth to show status.</div>
        ) : (
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            Status: <b>{emailLatest?.status ?? "unknown"}</b>
            {emailLatest?.timestamp ? <span style={{ opacity: 0.75 }}> · {emailLatest.timestamp}</span> : null}
          </div>
        )}
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
          Control this in <b>/settings/communications</b>.
        </div>
      </section>
    </main>
  );
}
