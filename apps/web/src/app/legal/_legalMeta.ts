export const LEGAL_VERSIONS = {
  terms: "v1.0",
  privacy: "v1.0",
  cookies: "v1.0",
  disclaimer: "v1.0",
  subscriptionTerms: "v1.0",
  contact: "v1.0",
} as const;

/** Legal/registered company name for contracts and legal documents. */
export const LEGAL_COMPANY_NAME = "Logos Capital Investments";

/** Full mailing address for legal documents and contact. */
export const LEGAL_ADDRESS = {
  name: "Logod Capital Investissement",
  line1: "16908 Rte Transcanadienne Suite 1001",
  city: "Kirkland, QC H9H 0C5",
  country: "Canada",
};
export const LEGAL_ADDRESS_FORMATTED = `${LEGAL_ADDRESS.name}\n${LEGAL_ADDRESS.line1}\n${LEGAL_ADDRESS.city}\n${LEGAL_ADDRESS.country}`;

export const LEGAL_EMAIL_SUPPORT = "support@regimeintelligence.com";
export const LEGAL_EMAIL_PRIVACY = "privacy@regimeintelligence.com";

export const LEGAL_LAST_UPDATED = {
  terms: "2026-02-28",
  privacy: "2026-02-28",
  cookies: "2026-02-28",
  disclaimer: "2026-02-28",
  subscriptionTerms: "2026-02-28",
  contact: "2026-02-28",
} as const;

export type LegalDocKey = keyof typeof LEGAL_VERSIONS;

// Helper to render "Last updated" + version consistently
export function legalHeader(doc: LegalDocKey, title: string) {
  const v = LEGAL_VERSIONS[doc];
  const d = LEGAL_LAST_UPDATED[doc];
  return { title, version: v, lastUpdated: d };
}
