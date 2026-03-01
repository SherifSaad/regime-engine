import Link from "next/link";

export function LegalLinks(props: { compact?: boolean }) {
  const style = props.compact
    ? { display: "flex", gap: 10, flexWrap: "wrap", fontSize: 12, opacity: 0.9 }
    : { display: "flex", gap: 14, flexWrap: "wrap", fontSize: 13, opacity: 0.9 };

  return (
    <nav style={style}>
      <Link href="/legal/terms">Terms</Link>
      <Link href="/legal/privacy">Privacy</Link>
      <Link href="/legal/cookies">Cookies</Link>
      <Link href="/legal/disclaimer">Disclaimer</Link>
      <Link href="/legal/subscription-terms">Subscription Terms</Link>
      <Link href="/legal/contact">Contact</Link>
    </nav>
  );
}
