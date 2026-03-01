import { LegalLinks } from "./LegalLinks";

export default function AppHeaderLegal() {
  return (
    <div style={{ borderBottom: "1px solid rgba(0,0,0,0.08)" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "10px 16px" }}>
        <LegalLinks compact />
      </div>
    </div>
  );
}
