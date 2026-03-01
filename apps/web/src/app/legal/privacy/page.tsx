import Link from "next/link";
import LegalPageShell from "../_LegalPageShell";
import {
  LEGAL_COMPANY_NAME,
  LEGAL_ADDRESS,
  LEGAL_EMAIL_SUPPORT,
  LEGAL_EMAIL_PRIVACY,
} from "../_legalMeta";

const addressBlock = `${LEGAL_ADDRESS.line1}, ${LEGAL_ADDRESS.city}, ${LEGAL_ADDRESS.country}`;

export default function Page() {
  return (
    <LegalPageShell doc="privacy" title="Privacy Policy (Canada + Quebec)">
      <p>
        <strong>Regime Intelligence / {LEGAL_COMPANY_NAME}</strong>
      </p>

      <h2 id="1">1. Introduction</h2>
      <p>
        This Privacy Policy explains how {LEGAL_COMPANY_NAME} (“Logos,” “we,” “us,” “our”) collects, uses, discloses, retains, and protects personal information when you use the Regime Intelligence website and services (the “Service”). It also explains your rights and choices regarding your personal information.
      </p>
      <p>
        We respect your privacy and are committed to safeguarding the personal information you provide to us, in accordance with the Personal Information Protection and Electronic Documents Act (PIPEDA) and Quebec’s updated privacy framework under Law 25 (ARPPIPS) requiring clear, transparent privacy practices and explicit consent for data uses.
      </p>

      <h2 id="2">2. Definitions</h2>
      <p>
        <strong>Personal Information</strong> means information that identifies or could reasonably identify an individual and does not include business contact information used only to communicate about the Service.
      </p>
      <p>
        <strong>Sensitive Personal Information</strong> means personal information for which extra protection and express consent may be required (e.g., financial details beyond transactional data, profile data used for profiling).
      </p>

      <h2 id="3">3. Scope</h2>
      <p>This Policy applies to all personal information collected by us through the Service, including:</p>
      <ul>
        <li>Information you provide directly (sign-up, forms, communications)</li>
        <li>Technical data collected via cookies or similar technologies with your consent</li>
        <li>Usage data about how you interact with the Service</li>
      </ul>

      <h2 id="4">4. Privacy Officer</h2>
      <p>We have appointed a Privacy Officer responsible for overseeing our privacy program and compliance with applicable privacy laws.</p>
      <p>Contact the Privacy Officer:</p>
      <p>📧 <a href={`mailto:${LEGAL_EMAIL_PRIVACY}`}>{LEGAL_EMAIL_PRIVACY}</a></p>
      <p>
        📍 {LEGAL_COMPANY_NAME}<br />
        {addressBlock}
      </p>

      <h2 id="5">5. What Personal Information We Collect</h2>
      <p>We collect personal information only where necessary for the purposes described below. This includes:</p>
      <p><strong>Account &amp; Contact Information:</strong></p>
      <ul>
        <li>Name, email address, region, billing information (when applicable)</li>
      </ul>
      <p><strong>Usage &amp; Technical Data:</strong></p>
      <ul>
        <li>Device and browser details, log data, interaction data, cookies/unique identifiers</li>
      </ul>
      <p><strong>Consent Records:</strong></p>
      <ul>
        <li>Cookie and marketing consent status with timestamp and region</li>
      </ul>
      <p><strong>Saved Screens or Custom Content:</strong></p>
      <ul>
        <li>Data you create and store within the Service (linked to your account)</li>
      </ul>
      <p>We do not collect personal information beyond what is necessary for the stated purposes.</p>

      <h2 id="6">6. How We Collect Personal Information</h2>
      <h3 id="6-direct">Direct Collection</h3>
      <p>We collect personal information you provide when:</p>
      <ul>
        <li>You create an account, purchase a subscription, or fill out forms</li>
        <li>You contact us for support or inquiries</li>
        <li>You opt-in to marketing communications</li>
      </ul>
      <h3 id="6-cookies">Cookies &amp; Tracking Technologies</h3>
      <p>
        We use cookies and similar technologies to operate and improve the Service and, with your explicit consent where required (especially in Quebec), for analytics and marketing purposes. Your consent choices are stored, linked to your account (or anonymous ID if not signed in). See <Link href="/legal/cookies">/legal/cookies</Link> for details.
      </p>

      <h2 id="7">7. Purposes of Collection, Use &amp; Disclosure</h2>
      <p>We collect, use, and disclose personal information only for purposes that are reasonable and appropriate, such as:</p>
      <ul>
        <li>Providing, operating, and improving the Service</li>
        <li>Account creation, authentication, and billing</li>
        <li>Managing your preferences and deliverables</li>
        <li>Marketing communications where you have consented</li>
        <li>Legal and regulatory compliance</li>
        <li>Internal analysis and Service optimization</li>
      </ul>
      <p>We do not use your personal information for purposes beyond those for which you have provided consent without obtaining further consent.</p>

      <h2 id="8">8. Consent</h2>
      <p>By using the Service, you consent to the collection, use, and disclosure of your personal information as described in this Privacy Policy, including:</p>
      <ul>
        <li>Your informed consent at the time of data collection</li>
        <li>Explicit opt-in consent for tracking technologies or any sensitive information use that is not required for core Service functionality, as required by Quebec Law 25.</li>
      </ul>
      <p>You may withdraw consent at any time where applicable, without affecting the lawfulness of processing based on consent before its withdrawal.</p>

      <h2 id="9">9. Sharing Personal Information</h2>
      <p>We may share personal information with:</p>
      <ul>
        <li>Service providers who help operate the Service (e.g., payment processors, hosting) under contractual confidentiality safeguards</li>
        <li>Our affiliates</li>
        <li>Legal and regulatory authorities when required by law or to protect rights and safety</li>
      </ul>
      <p>We do not sell your personal information.</p>
      <p>When personal information is shared outside Quebec or Canada, we ensure transparency and reasonable safeguards, including contractual protections and, where required, appropriate notices as part of required privacy impact assessments.</p>

      <h2 id="10">10. Your Rights</h2>
      <p>Under applicable privacy laws, you have the right to:</p>
      <ul>
        <li><strong>Access Your Personal Information</strong> – request a copy of what we hold about you</li>
        <li><strong>Correction</strong> – request correction of inaccuracies</li>
        <li><strong>Deletion / Right to Be Forgotten</strong> where retention is not required by law</li>
        <li><strong>Portability</strong> – receive certain personal information in a structured format</li>
        <li><strong>Object to Processing</strong> – in certain contexts, including profiling</li>
      </ul>
      <p>
        Requests can be made via <a href={`mailto:${LEGAL_EMAIL_PRIVACY}`}>{LEGAL_EMAIL_PRIVACY}</a> or through in-app tools where available.
      </p>
      <p>We will verify your identity before fulfilling requests, in line with reasonable security requirements.</p>

      <h2 id="11">11. Security</h2>
      <p>We implement administrative, technical, and physical safeguards to protect personal information, adjusting measures according to the sensitivity of the data and risk (e.g., encryption and access controls). However, no method of transmission or storage is fully secure.</p>

      <h2 id="12">12. Data Retention</h2>
      <p>We retain personal information only as long as required to fulfill the purposes described or as required by law. Retention periods are determined based on legal requirements, Service needs, and user expectations.</p>

      <h2 id="13">13. Children</h2>
      <p>Our Service is not directed to children under 13. We do not knowingly collect personal information from children. If you believe we have collected such information, contact us to request deletion.</p>

      <h2 id="14">14. Changes to this Policy</h2>
      <p>We may update this Privacy Policy to reflect changes in legal requirements, Service practices, or technology. When we do, we will revise the “Last updated” date and, where appropriate, provide notice via the Service.</p>

      <h2 id="15">15. Contact Us</h2>
      <p>For questions about this Privacy Policy or to exercise your privacy rights:</p>
      <p>📧 <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>
      <p>
        📍 {LEGAL_COMPANY_NAME}<br />
        {addressBlock}
      </p>
    </LegalPageShell>
  );
}
