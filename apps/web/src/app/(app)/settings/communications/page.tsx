"use client";

import { useMemo, useState } from "react";

function fakeUserId() {
  // Placeholder until real auth is wired:
  // replace with your real session user id.
  return "USER_ID_TBD";
}

function inferRegion(): "CA-QC" | "CA" | "UNKNOWN" {
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

export default function CommunicationsSettingsPage() {
  const userId = useMemo(() => fakeUserId(), []);
  const region = useMemo(() => inferRegion(), []);
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const save = async (next: boolean) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/consent/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          email: null,
          status: next ? "opt_in" : "opt_out",
          source: "settings",
          region,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error("save failed");
      setOn(next);
      setMsg(next ? "Marketing emails enabled." : "Marketing emails disabled.");
    } catch {
      setMsg("Failed to update preference.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
      <h1 style={{ margin: 0 }}>Communications</h1>
      <div style={{ fontSize: 13, opacity: 0.8, marginTop: 6 }}>
        Manage marketing email preferences (unsubscribe equivalent).
      </div>

      <hr style={{ margin: "16px 0" }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ fontWeight: 800 }}>Product updates</div>
            <div style={{ fontSize: 13, opacity: 0.85, marginTop: 4 }}>
              Receive product announcements and updates. Optional.
            </div>
          </div>

          <button
            onClick={() => save(!on)}
            disabled={busy || userId === "USER_ID_TBD"}
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid rgba(0,0,0,0.25)",
              background: "white",
              fontWeight: 800,
              cursor: "pointer",
              minWidth: 220,
            }}
          >
            {on ? "Turn OFF" : "Turn ON"}
          </button>
        </div>

        {userId === "USER_ID_TBD" && (
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
            Note: this will be fully active once real authentication user_id is wired.
          </div>
        )}
      </section>

      {msg && <div style={{ marginTop: 14, fontSize: 13 }}>{msg}</div>}
    </main>
  );
}
