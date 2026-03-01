import LegalPageShell from "../_LegalPageShell";
import {
  LEGAL_COMPANY_NAME,
  LEGAL_ADDRESS_FORMATTED,
  LEGAL_EMAIL_SUPPORT,
  LEGAL_EMAIL_PRIVACY,
} from "../_legalMeta";

export default function Page() {
  return (
    <LegalPageShell doc="contact" title="Legal & Privacy Contact Information">
      <p>
        <strong>Regime Intelligence / {LEGAL_COMPANY_NAME}</strong>
      </p>

      <h2 id="1">1. Company Information</h2>
      <p><strong>Legal Entity:</strong><br />{LEGAL_COMPANY_NAME}</p>
      <p><strong>Operating Service:</strong><br />Regime Intelligence</p>
      <p><strong>Mailing Address:</strong></p>
      <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", margin: 0 }}>{LEGAL_ADDRESS_FORMATTED}</pre>

      <h2 id="2">2. Privacy Officer</h2>
      <p>
        In accordance with applicable Canadian privacy laws, including PIPEDA and Quebec’s Law 25, we have designated a Privacy Officer responsible for:
      </p>
      <ul>
        <li>Privacy compliance oversight</li>
        <li>Handling access, correction, deletion, and portability requests</li>
        <li>Managing privacy complaints</li>
        <li>Overseeing privacy impact assessments</li>
        <li>Ensuring appropriate safeguards for cross-border transfers</li>
      </ul>
      <p><strong>Privacy Officer Contact:</strong></p>
      <p>📧 <a href={`mailto:${LEGAL_EMAIL_PRIVACY}`}>{LEGAL_EMAIL_PRIVACY}</a></p>
      <p>You may contact the Privacy Officer for any questions about:</p>
      <ul>
        <li>How your personal information is collected, used, or stored</li>
        <li>Exercising your privacy rights</li>
        <li>Filing a complaint regarding privacy handling</li>
        <li>Data retention or cross-border disclosures</li>
      </ul>

      <h2 id="3">3. General Legal &amp; Support Inquiries</h2>
      <p>For non-privacy matters, including:</p>
      <ul>
        <li>Subscription issues</li>
        <li>Billing questions</li>
        <li>Terms of Service clarification</li>
        <li>Technical support</li>
      </ul>
      <p>Please contact:</p>
      <p>📧 <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>

      <h2 id="4">4. Regulatory Complaints</h2>
      <p>
        If you are not satisfied with our response to a privacy concern, you may have the right to contact the appropriate privacy regulator.
      </p>
      <p><strong>For Canada (federal matters):</strong><br />Office of the Privacy Commissioner of Canada</p>
      <p><strong>For Quebec residents:</strong><br />Commission d’accès à l’information du Québec</p>
      <p>We encourage you to contact us first so we may attempt to resolve your concern.</p>

      <h2 id="5">5. Response Time</h2>
      <p>
        We aim to respond to privacy and legal inquiries within a reasonable timeframe, typically within 30 days, subject to identity verification and complexity of the request.
      </p>

      <h2 id="6">6. Identity Verification</h2>
      <p>
        For security and privacy reasons, we may request information necessary to verify your identity before processing access, correction, deletion, or portability requests.
      </p>

      <h2 id="7">7. Language</h2>
      <p>
        If you are a Quebec resident, French versions of legal documents are available upon request in accordance with applicable language laws.
      </p>
    </LegalPageShell>
  );
}
