import LegalPageShell from "../_LegalPageShell";
import { LEGAL_COMPANY_NAME, LEGAL_ADDRESS, LEGAL_EMAIL_SUPPORT } from "../_legalMeta";

const addressLine = `${LEGAL_COMPANY_NAME}, ${LEGAL_ADDRESS.line1}, ${LEGAL_ADDRESS.city}, ${LEGAL_ADDRESS.country}`;

export default function Page() {
  return (
    <LegalPageShell doc="cookies" title="Cookies & Tracking Policy">
      <p>
        <strong>Regime Intelligence / {LEGAL_COMPANY_NAME}</strong>
      </p>

      <h2 id="1">1. Introduction</h2>
      <p>
        This Cookies &amp; Tracking Policy explains what cookies and similar technologies (collectively “cookies”) are, how we use them on the Service, why we collect such information, and how you can manage your choices.
      </p>
      <p>
        <strong>Important:</strong> Except for strictly necessary cookies required for the core functioning of the Service, we will not place cookies or tracking technologies on your device without your explicit consent. This is to comply with Quebec’s enhanced privacy requirements (Law 25) and Canadian privacy expectations.
      </p>

      <h2 id="2">2. What are cookies?</h2>
      <p>
        Cookies are small text files stored on your device by your browser when you visit websites or use online services. They help remember your preferences, track usage patterns, and enable certain features of the Service.
      </p>

      <h2 id="3">3. How we use cookies and tracking technologies</h2>
      <p>We use the following categories of cookies and similar technologies:</p>
      <h3 id="3a">a) Necessary Cookies</h3>
      <p>
        These cookies are essential to run and secure the Service (login, account settings, session management) and do not require your consent.
      </p>
      <h3 id="3b">b) Analytics &amp; Performance Cookies</h3>
      <p>
        With your explicit prior consent, we use analytics cookies to understand how users interact with the Service and improve performance. These cookies may collect usage data such as pages visited, time spent, and error logs.
      </p>
      <h3 id="3c">c) Marketing &amp; Advertising Cookies</h3>
      <p>
        With your explicit prior consent, marketing cookies may be used to understand your interests and deliver relevant content or ads.
      </p>
      <p>
        For all non-essential cookies (analytics, marketing), we will not activate them until you opt in via the cookie consent banner or preferences center.
      </p>

      <h2 id="4">4. Third-party cookies</h2>
      <p>
        Some cookies and tracking technologies are set by third-party services that provide analytics or other functionality on our behalf. When such cookies are used, we disclose them here and explain their purposes, so you can make an informed choice. These third parties are governed by their own privacy policies, and we encourage you to review their disclosures.
      </p>
      <p>Examples of third-party cookies we may use (only with your consent):</p>
      <ul>
        <li>Analytics providers</li>
        <li>Marketing and advertising partners</li>
      </ul>
      <p>If you reject non-essential cookies, these third-party cookies will not be activated.</p>

      <h2 id="5">5. Your consent and choices</h2>
      <p>When you first visit the Service, a cookie consent banner will appear explaining:</p>
      <ul>
        <li>what cookies we use,</li>
        <li>for what purposes,</li>
        <li>and how to accept or reject each category.</li>
      </ul>
      <p>You may:</p>
      <ul>
        <li>Accept all non-essential cookies,</li>
        <li>Reject all non-essential cookies, or</li>
        <li>Manage preferences to select which non-essential cookies you allow.</li>
      </ul>
      <p>
        Your cookie preferences are stored (linked to your account or an anonymous identifier) with the date, time, and region flag. You can modify your choices at any time using the cookie preferences center.
      </p>

      <h2 id="6">6. Withdrawing consent</h2>
      <p>
        You can withdraw your consent for non-essential cookies at any time. Withdrawal of consent will not affect the lawfulness of processing based on consent before its withdrawal.
      </p>
      <p>You can manage or withdraw your preferences:</p>
      <ul>
        <li>directly in the cookie preferences center in the Service, or</li>
        <li>by clearing cookies via your browser settings (browser mechanisms vary by platform).</li>
      </ul>
      <p>After withdrawal of consent, non-essential cookies will be disabled moving forward.</p>

      <h2 id="7">7. How to control cookies through your browser</h2>
      <p>
        Most browsers allow you to control cookie settings (block, delete, or alert before acceptance). Please consult your browser documentation for instructions on managing cookies. Note that blocking certain cookies may affect the functionality of the Service.
      </p>

      <h2 id="8">8. Updates to this Cookie Policy</h2>
      <p>
        We may update this policy to reflect changes in legal requirements, cookie technologies, or our practices. If we make material changes, we will update the “Last updated” date and, where appropriate, provide notice via the Service.
      </p>

      <h2 id="9">9. Contact us</h2>
      <p>If you have questions about this policy or want to exercise data rights regarding cookies or tracking:</p>
      <p>Email: <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>
      <p>Address: {addressLine}</p>
    </LegalPageShell>
  );
}
