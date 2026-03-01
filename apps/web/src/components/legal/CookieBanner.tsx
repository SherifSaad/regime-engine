"use client";

import { useEffect, useMemo, useState } from "react";

type Categories = { necessary: true; analytics: boolean; marketing: boolean };
type Region = "CA-QC" | "CA" | "UNKNOWN";

const LS_KEY = "ri_cookie_consent_v1";
const LS_ANON = "ri_anon_id_v1";

function uuidLike() {
  // No crypto dependency: good-enough anonymous device id for consent record linkage
  return "anon_" + Math.random().toString(16).slice(2) + "_" + Date.now().toString(16);
}

function getAnonId(): string {
  if (typeof window === "undefined") return "anon_server";
  const existing = window.localStorage.getItem(LS_ANON);
  if (existing) return existing;
  const id = uuidLike();
  window.localStorage.setItem(LS_ANON, id);
  return id;
}

function inferRegion(): Region {
  // Quebec-first defaults: if we *suspect* QC, flag CA-QC. Otherwise CA/UNKNOWN.
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    const lang = navigator.language || "";
    if (tz.includes("America/Montreal") || tz.includes("America/Toronto") || lang.toLowerCase().startsWith("fr-ca")) {
      // Montreal users => CA-QC; Toronto timezone still CA, but lang fr-ca is a strong QC signal.
      if (lang.toLowerCase().startsWith("fr-ca") || tz.includes("America/Montreal")) return "CA-QC";
      return "CA";
    }
    return "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

async function postConsent(payload: {
  anon_id: string;
  region: Region;
  categories: Categories;
  source: "banner_accept_all" | "banner_reject_all" | "modal_save";
}) {
  try {
    await fetch("/api/consent/cookies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // no-throw: consent is still stored locally; server log can be retried later if needed
  }
}

function loadLocal(): Categories | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(LS_KEY);
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    if (typeof obj?.analytics !== "boolean" || typeof obj?.marketing !== "boolean") return null;
    return { necessary: true, analytics: obj.analytics, marketing: obj.marketing };
  } catch {
    return null;
  }
}

function saveLocal(c: Categories) {
  window.localStorage.setItem(LS_KEY, JSON.stringify({ analytics: c.analytics, marketing: c.marketing, savedAt: Date.now() }));
}

function categoryLabel(key: keyof Categories) {
  if (key === "necessary") return "Necessary";
  if (key === "analytics") return "Analytics";
  return "Marketing";
}

export default function CookieBanner() {
  const [open, setOpen] = useState(false);
  const [prefsOpen, setPrefsOpen] = useState(false);

  const anonId = useMemo(() => getAnonId(), []);
  const region = useMemo(() => inferRegion(), []);

  const [draft, setDraft] = useState<Categories>({ necessary: true, analytics: false, marketing: false });

  useEffect(() => {
    const existing = loadLocal();
    if (existing) {
      setDraft(existing);
      setOpen(false);
      return;
    }
    // No prior decision => show banner
    setOpen(true);
  }, []);

  const acceptAll = async () => {
    const c: Categories = { necessary: true, analytics: true, marketing: true };
    saveLocal(c);
    setDraft(c);
    setOpen(false);
    setPrefsOpen(false);
    await postConsent({ anon_id: anonId, region, categories: c, source: "banner_accept_all" });
  };

  const rejectNonEssential = async () => {
    const c: Categories = { necessary: true, analytics: false, marketing: false };
    saveLocal(c);
    setDraft(c);
    setOpen(false);
    setPrefsOpen(false);
    await postConsent({ anon_id: anonId, region, categories: c, source: "banner_reject_all" });
  };

  const savePrefs = async () => {
    const c: Categories = { ...draft, necessary: true };
    saveLocal(c);
    setOpen(false);
    setPrefsOpen(false);
    await postConsent({ anon_id: anonId, region, categories: c, source: "modal_save" });
  };

  if (!open) return null;

  return (
    <div style={{ position: "fixed", inset: "auto 0 0 0", zIndex: 9999 }}>
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: 12,
        }}
      >
        <div
          style={{
            border: "1px solid rgba(0,0,0,0.15)",
            background: "white",
            borderRadius: 12,
            padding: 14,
            display: "flex",
            gap: 14,
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ flex: "1 1 520px", minWidth: 260 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Cookies & Tracking</div>
            <div style={{ fontSize: 13, lineHeight: 1.4, opacity: 0.9 }}>
              We use <b>necessary</b> cookies to run the Service. With your permission, we also use optional cookies for
              <b> analytics</b> and <b>marketing</b>. In Quebec, non-essential cookies are opt-in by default.
              <span style={{ marginLeft: 8 }}>
                <a href="/legal/cookies" style={{ textDecoration: "underline" }}>Learn more</a>
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {/* Reject must be as easy as accept (same prominence, no extra clicks) */}
            <button
              onClick={rejectNonEssential}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.25)",
                background: "white",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Reject non-essential
            </button>

            <button
              onClick={() => setPrefsOpen(true)}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.25)",
                background: "white",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Manage preferences
            </button>

            <button
              onClick={acceptAll}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.25)",
                background: "white",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Accept all
            </button>
          </div>
        </div>
      </div>

      {prefsOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
          }}
        >
          <div style={{ width: "min(720px, 100%)", background: "white", borderRadius: 14, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div style={{ fontWeight: 800, fontSize: 16 }}>Cookie Preferences</div>
              <button
                onClick={() => setPrefsOpen(false)}
                style={{ border: "1px solid rgba(0,0,0,0.2)", background: "white", borderRadius: 10, padding: "6px 10px", cursor: "pointer" }}
              >
                Close
              </button>
            </div>

            <div style={{ marginTop: 12, fontSize: 13, opacity: 0.9 }}>
              Necessary cookies are always enabled. You can opt in to analytics and marketing cookies below.
            </div>

            <div style={{ marginTop: 14, display: "grid", gap: 10 }}>
              {(["necessary", "analytics", "marketing"] as const).map((k) => (
                <div key={k} style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12, display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{categoryLabel(k)}</div>
                    <div style={{ fontSize: 12, opacity: 0.85, marginTop: 4 }}>
                      {k === "necessary" && "Required for core site functionality and security."}
                      {k === "analytics" && "Helps us understand usage and improve performance (opt-in)."}
                      {k === "marketing" && "Helps measure campaigns or personalize marketing (opt-in)."}
                    </div>
                  </div>

                  <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                    <input
                      type="checkbox"
                      checked={k === "necessary" ? true : Boolean(draft[k])}
                      disabled={k === "necessary"}
                      onChange={(e) => {
                        if (k === "necessary") return;
                        setDraft((d) => ({ ...d, [k]: e.target.checked }));
                      }}
                    />
                    {k === "necessary" ? "On" : draft[k] ? "On" : "Off"}
                  </label>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, flexWrap: "wrap", marginTop: 14 }}>
              <button
                onClick={rejectNonEssential}
                style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 600, cursor: "pointer" }}
              >
                Reject non-essential
              </button>
              <button
                onClick={savePrefs}
                style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
              >
                Save preferences
              </button>
            </div>

            <div style={{ marginTop: 10, fontSize: 12, opacity: 0.8 }}>
              You can change your choice later in Settings (coming) or by clearing browser storage.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
