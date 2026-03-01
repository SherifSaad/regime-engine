"use client";

import { useMemo, useState } from "react";

function fakeUserId() {
  // Placeholder until real auth is wired:
  // replace with your real session user id.
  return "USER_ID_TBD";
}

export default function PrivacySettingsPage() {
  const userId = useMemo(() => fakeUserId(), []);
  const [busy, setBusy] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const exportData = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/privacy/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      if (!res.ok) throw new Error("Export failed");

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
      setMsg("Export started (download).");
    } catch {
      setMsg("Export failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const requestDelete = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/privacy/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, confirm: deleteConfirm }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error("Delete failed");
      setMsg("Deletion request recorded.");
      setDeleteConfirm("");
    } catch {
      setMsg("Deletion request failed. Type DELETE exactly and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
      <h1 style={{ margin: 0 }}>Privacy</h1>
      <div style={{ fontSize: 13, opacity: 0.8, marginTop: 6 }}>
        Manage your personal data and privacy requests.
      </div>

      <hr style={{ margin: "16px 0" }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Download my data</h2>
        <div style={{ fontSize: 13, opacity: 0.85, marginTop: 6 }}>
          Export the information we currently store about your account (consent and acceptance records).
        </div>
        <button
          onClick={exportData}
          disabled={busy || userId === "USER_ID_TBD"}
          style={{ marginTop: 10, padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
        >
          Export my data
        </button>
        {userId === "USER_ID_TBD" && (
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
            Note: export will be fully active once real authentication user_id is wired.
          </div>
        )}
      </section>

      <div style={{ height: 14 }} />

      <section style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 14 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Delete my account</h2>
        <div style={{ fontSize: 13, opacity: 0.85, marginTop: 6 }}>
          Request deletion of your account and personal data.
        </div>

        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.85 }}>
          <b>Retention notice:</b> Some records may be retained where required for legal/security purposes (for example,
          billing records, fraud prevention, and audit logs).
        </div>

        <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder="Type DELETE to confirm"
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", minWidth: 260 }}
          />
          <button
            onClick={requestDelete}
            disabled={busy || userId === "USER_ID_TBD"}
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(0,0,0,0.25)", background: "white", fontWeight: 800, cursor: "pointer" }}
          >
            Request deletion
          </button>
        </div>

        {userId === "USER_ID_TBD" && (
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
            Note: deletion will be fully active once real authentication user_id is wired.
          </div>
        )}
      </section>

      {msg && <div style={{ marginTop: 14, fontSize: 13 }}>{msg}</div>}
    </main>
  );
}
