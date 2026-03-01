import { LegalLinks } from "./LegalLinks";

export default function AppFooter() {
  return (
    <footer className="print:hidden" style={{ borderTop: "1px solid rgba(0,0,0,0.08)", marginTop: 28 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "18px 16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div style={{ fontSize: 12, opacity: 0.75 }}>
            © {new Date().getFullYear()} Regime Intelligence
          </div>
          <LegalLinks compact />
        </div>
      </div>
    </footer>
  );
}
