import Link from "next/link";
import { ReactNode } from "react";
import { LegalDocKey, legalHeader } from "./_legalMeta";
import LegalDocumentHeader from "@/components/legal/LegalDocumentHeader";

export default function LegalPageShell(props: {
  doc: LegalDocKey;
  title: string;
  children: ReactNode;
}) {
  const meta = legalHeader(props.doc, props.title);

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "24px 16px" }}>
      <LegalDocumentHeader />
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0 }}>{meta.title}</h1>
          <div style={{ fontSize: 12, opacity: 0.75, marginTop: 6 }}>
            Last updated: <strong>{meta.lastUpdated}</strong> · Version: <strong>{meta.version}</strong>
          </div>
        </div>

        <div style={{ fontSize: 12, opacity: 0.85, alignSelf: "flex-end" }}>
          <Link href="/" style={{ textDecoration: "underline" }}>Home</Link>
        </div>
      </div>

      <hr style={{ margin: "16px 0" }} />

      <article className="legal-doc" style={{ lineHeight: 1.55, fontSize: 14 }}>{props.children}</article>

      <hr style={{ margin: "24px 0 14px" }} />
      <nav style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12 }}>
        <Link href="/legal/terms">Terms</Link>
        <Link href="/legal/privacy">Privacy</Link>
        <Link href="/legal/cookies">Cookies</Link>
        <Link href="/legal/disclaimer">Disclaimer</Link>
        <Link href="/legal/subscription-terms">Subscription Terms</Link>
        <Link href="/legal/contact">Contact</Link>
      </nav>
    </main>
  );
}
