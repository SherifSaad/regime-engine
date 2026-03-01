import Link from "next/link";
import LegalPageShell from "../_LegalPageShell";
import { LEGAL_COMPANY_NAME, LEGAL_ADDRESS_FORMATTED, LEGAL_EMAIL_SUPPORT } from "../_legalMeta";

export default function Page() {
  return (
    <LegalPageShell doc="terms" title="Terms of Service (Regime Intelligence)">
      <p>
        <strong>Company:</strong> {LEGAL_COMPANY_NAME}<br />
        <strong>Address:</strong> {LEGAL_ADDRESS_FORMATTED.replace(/\n/g, ", ")}<br />
        <strong>Support:</strong> <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a>
      </p>

      <h2 id="1">1) Acceptance of these Terms</h2>
      <p>
        These Terms of Service (“Terms”) govern your access to and use of the Regime Intelligence website, applications, and related services (collectively, the “Service”). By creating an account, accessing, or using the Service, you agree to these Terms.
      </p>
      <p>If you do not agree, do not use the Service.</p>

      <h2 id="2">2) Who we are</h2>
      <p>
        The Service is operated by {LEGAL_COMPANY_NAME} (“Logos,” “we,” “us,” “our”) at the address above.
      </p>

      <h2 id="3">3) Important disclaimer (informational only)</h2>
      <p>
        Regime Intelligence provides informational and educational content only. The Service does not provide investment advice, legal advice, accounting advice, or tax advice, and does not recommend or endorse any security, strategy, or transaction.
      </p>
      <p>You are solely responsible for your decisions and actions.</p>
      <p>
        (Full wording is provided in <Link href="/legal/disclaimer">/legal/disclaimer</Link>, which forms part of your overall understanding of the Service.)
      </p>

      <h2 id="4">4) Eligibility</h2>
      <p>
        You must be able to form a legally binding contract to use the Service. If you use the Service on behalf of an organization, you represent that you have authority to bind that organization, and “you” includes the organization.
      </p>

      <h2 id="5">5) Your account</h2>
      <h3 id="5-1">5.1 Account information</h3>
      <p>You agree to provide accurate information and keep it up to date.</p>
      <h3 id="5-2">5.2 Security</h3>
      <p>You are responsible for safeguarding your login credentials and for activities under your account. Notify us promptly if you suspect unauthorized access.</p>
      <h3 id="5-3">5.3 Suspension/termination</h3>
      <p>We may suspend or terminate access if we reasonably believe:</p>
      <ul>
        <li>your account is being used fraudulently or unlawfully,</li>
        <li>you are violating these Terms, or</li>
        <li>continued access creates security or operational risk.</li>
      </ul>

      <h2 id="6">6) Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>access or use the Service in a way that violates applicable laws;</li>
        <li>attempt to bypass security, rate limits, or access controls;</li>
        <li>interfere with or disrupt the Service or its infrastructure;</li>
        <li>reverse engineer or extract source code except where prohibited by law;</li>
        <li>scrape, harvest, or collect data from the Service using automated means unless we explicitly allow it in writing.</li>
      </ul>

      <h2 id="7">7) Service changes and availability</h2>
      <p>We may update, modify, or discontinue parts of the Service. We do not guarantee that the Service will be uninterrupted or error-free.</p>

      <h2 id="8">8) Subscriptions, billing, and renewals</h2>
      <p>
        If you purchase a paid plan, your purchase is also governed by <Link href="/legal/subscription-terms">/legal/subscription-terms</Link>.
      </p>
      <h3 id="8-1">8.1 Clear disclosure at checkout</h3>
      <p>Key subscription terms (price, billing frequency, renewal behavior, cancellation method) will be displayed inline during checkout and not only “hidden” behind links.</p>
      <h3 id="8-2">8.2 Cancellation</h3>
      <p>If your plan is cancellable, we will provide a straightforward cancellation method inside the app.</p>
      <h3 id="8-3">8.3 Quebec consumer protection (online subscriptions)</h3>
      <p>If Quebec consumer-protection rules apply to your contract, we design the Service to support compliant online subscription renewal practices (including clear notice and cancellation UX expectations as those rules evolve).</p>

      <h2 id="9">9) Privacy and data protection</h2>
      <p>
        Our collection, use, retention, and disclosure of personal information are described in <Link href="/legal/privacy">/legal/privacy</Link>.
      </p>
      <p><strong>High-level commitments:</strong></p>
      <ul>
        <li>We collect and use personal information for identified purposes and with appropriate consent.</li>
        <li>If we transfer personal information outside Quebec, we perform the required assessment steps (including privacy impact assessment expectations under Quebec law where applicable).</li>
        <li>Cookie/tracking preferences are managed through <Link href="/legal/cookies">/legal/cookies</Link> and in-app consent controls.</li>
      </ul>

      <h2 id="10">10) Marketing communications (CASL)</h2>
      <p>If you opt in to product updates or other commercial electronic messages, we will:</p>
      <ul>
        <li>obtain and record consent where required;</li>
        <li>include sender identification information; and</li>
        <li>provide an unsubscribe mechanism (and honor unsubscribe requests).</li>
      </ul>
      <p>You can also manage marketing preferences inside the app under <Link href="/settings/communications">/settings/communications</Link>.</p>

      <h2 id="11">11) Your content and saved “screens”</h2>
      <p>If the Service lets you save configurations, screens, alerts, watchlists, or similar items (“Saved Screens”), those items are associated with your account. Our handling of that association is described in <Link href="/legal/privacy">/legal/privacy</Link>, including retention.</p>
      <p>You grant us permission to host, store, and process Saved Screens solely to operate the Service for you.</p>

      <h2 id="12">12) Intellectual property</h2>
      <p>The Service, including its software, design, text, graphics, logos, and underlying models, is owned by Logos or its licensors and is protected by intellectual property laws.</p>
      <p>You receive a limited, non-exclusive, non-transferable, revocable license to use the Service for your personal or internal business use, subject to these Terms.</p>

      <h2 id="13">13) Feedback</h2>
      <p>If you provide suggestions or feedback, you grant us a perpetual, worldwide, royalty-free right to use it without restriction or compensation.</p>

      <h2 id="14">14) Third-party services and links</h2>
      <p>The Service may reference or integrate third-party services. We are not responsible for third-party services, their availability, or their content, and your use of them may be governed by their own terms.</p>

      <h2 id="15">15) Disclaimer of warranties</h2>
      <p>To the maximum extent permitted by law, the Service is provided “as is” and “as available,” without warranties of any kind, whether express, implied, or statutory, including implied warranties of merchantability, fitness for a particular purpose, and non-infringement.</p>
      <p>We do not warrant that outputs, content, or information provided by the Service will be accurate, complete, or suitable for any particular purpose.</p>

      <h2 id="16">16) Limitation of liability</h2>
      <p>To the maximum extent permitted by law:</p>
      <ul>
        <li>Logos will not be liable for indirect, incidental, special, consequential, or punitive damages, or for loss of profits, revenues, data, goodwill, or business opportunities, arising out of or related to your use of the Service.</li>
        <li>Logos’ total aggregate liability for all claims related to the Service will not exceed the amount you paid to Logos for the Service in the three (3) months preceding the event giving rise to the claim (or CAD $100 if you have not paid anything).</li>
      </ul>
      <p>Some jurisdictions do not allow certain limitations, so some of the above may not apply to you.</p>

      <h2 id="17">17) Indemnity</h2>
      <p>You agree to indemnify and hold Logos harmless from claims, liabilities, damages, losses, and expenses (including reasonable legal fees) arising from your use of the Service, your violation of these Terms, or your violation of applicable law.</p>

      <h2 id="18">18) Governing law and venue</h2>
      <p>These Terms are governed by the laws applicable in the Province of Quebec and the federal laws of Canada applicable therein, without regard to conflict of laws principles.</p>
      <p>Any dispute will be brought in the courts located in Quebec, unless applicable consumer protection laws require otherwise.</p>

      <h2 id="19">19) Changes to these Terms</h2>
      <p>We may update these Terms. We will update the “Last updated” date and version. If changes are material, we will provide notice within the Service or by other reasonable means.</p>
      <p>Your continued use of the Service after changes become effective means you accept the updated Terms.</p>

      <h2 id="20">20) Contact</h2>
      <p>Questions about these Terms:</p>
      <p><a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>
      <p style={{ whiteSpace: "pre-wrap" }}>{LEGAL_ADDRESS_FORMATTED}</p>

      <h2 id="21">21) Language (Quebec)</h2>
      <p>We operate in Quebec and will make these Terms available in French in accordance with applicable Quebec language requirements for standard-form contracts and commercial publications.</p>
    </LegalPageShell>
  );
}
