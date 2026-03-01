import LegalPageShell from "../_LegalPageShell";
import { LEGAL_COMPANY_NAME, LEGAL_ADDRESS, LEGAL_EMAIL_SUPPORT } from "../_legalMeta";

export default function Page() {
  return (
    <LegalPageShell doc="subscriptionTerms" title="Subscription Terms">
      <p>
        <strong>Regime Intelligence / {LEGAL_COMPANY_NAME}</strong>
      </p>
      <p>
        These Subscription Terms govern paid plans offered through Regime Intelligence (the “Service”) and form part of your agreement with {LEGAL_COMPANY_NAME} (“Logos,” “we,” “us,” “our”).
      </p>

      <h2 id="1">1. Subscription Plans</h2>
      <p>Regime Intelligence may offer paid subscription plans that provide access to premium features.</p>
      <p>Each subscription plan will clearly display:</p>
      <ul>
        <li>Price (in CAD or specified currency)</li>
        <li>Billing frequency (monthly, annual, or otherwise)</li>
        <li>Whether the subscription auto-renews</li>
        <li>Trial period (if applicable)</li>
        <li>Cancellation method</li>
      </ul>
      <p>These key terms are displayed inline during checkout, not solely by hyperlink.</p>

      <h2 id="2">2. Billing and Payment</h2>
      <h3 id="2-1">2.1 Payment Authorization</h3>
      <p>By subscribing, you authorize us (or our payment processor) to charge your selected payment method for:</p>
      <ul>
        <li>Subscription fees</li>
        <li>Applicable taxes</li>
        <li>Any additional charges clearly disclosed at checkout</li>
      </ul>
      <h3 id="2-2">2.2 Currency</h3>
      <p>Unless otherwise specified, all amounts are billed in Canadian Dollars (CAD).</p>
      <h3 id="2-3">2.3 Taxes</h3>
      <p>You are responsible for any applicable sales, consumption, or value-added taxes required by law.</p>

      <h2 id="3">3. Automatic Renewal</h2>
      <p>If your subscription includes automatic renewal:</p>
      <ul>
        <li>Your subscription will renew at the end of each billing cycle.</li>
        <li>The renewal charge will be at the then-current rate for your plan.</li>
        <li>You will be informed of renewal terms at checkout.</li>
        <li>You may cancel before the renewal date to avoid the next billing cycle.</li>
      </ul>
      <p>We design renewal flows to be transparent and compliant with Quebec consumer protection standards.</p>

      <h2 id="4">4. Free Trials (If Offered)</h2>
      <p>If a free trial is offered:</p>
      <ul>
        <li>The duration of the trial will be clearly disclosed.</li>
        <li>Billing will begin automatically at the end of the trial unless canceled before the trial period expires.</li>
        <li>Cancellation during the trial prevents billing.</li>
        <li>We do not apply hidden conversion mechanisms.</li>
      </ul>

      <h2 id="5">5. Cancellation</h2>
      <h3 id="5-1">5.1 How to Cancel</h3>
      <p>You may cancel your subscription at any time through:</p>
      <ul>
        <li>The in-app account settings page, or</li>
        <li>By contacting <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></li>
      </ul>
      <p>Cancellation methods are accessible and not designed to obstruct users.</p>
      <h3 id="5-2">5.2 Effect of Cancellation</h3>
      <p>Unless otherwise required by law:</p>
      <ul>
        <li>Cancellation stops future billing.</li>
        <li>You will retain access until the end of your current paid billing period.</li>
        <li>No partial refunds are provided for unused portions of a billing cycle, except where required by law.</li>
      </ul>

      <h2 id="6">6. Refund Policy</h2>
      <p>Unless otherwise required by applicable law:</p>
      <ul>
        <li>Subscription fees are non-refundable.</li>
        <li>We may issue refunds at our discretion in exceptional cases.</li>
        <li>Nothing in this section limits statutory consumer rights under applicable laws.</li>
      </ul>

      <h2 id="7">7. Changes to Pricing</h2>
      <p>We may modify subscription pricing in the future. If pricing changes:</p>
      <ul>
        <li>Changes will apply only to future billing cycles.</li>
        <li>We will provide reasonable notice before new rates apply.</li>
        <li>Continued use of the Service after the effective date constitutes acceptance of the new pricing.</li>
      </ul>

      <h2 id="8">8. Payment Processor</h2>
      <p>Payments may be processed by a third-party payment processor. Logos does not store full payment card details on its own servers.</p>
      <p>Your use of third-party payment services is subject to their terms and privacy policies.</p>

      <h2 id="9">9. Suspension or Termination</h2>
      <p>We may suspend or terminate access to paid features if:</p>
      <ul>
        <li>Payment fails and is not resolved,</li>
        <li>Fraudulent activity is suspected,</li>
        <li>You violate the Terms of Service.</li>
      </ul>
      <p>If access is suspended due to non-payment, restoration may require settlement of outstanding balances.</p>

      <h2 id="10">10. Consumer Protection</h2>
      <p>Nothing in these Subscription Terms excludes or limits rights that cannot legally be waived under applicable consumer protection laws in Canada or Quebec.</p>
      <p>If you are a Quebec consumer, certain protections may apply that override inconsistent contractual provisions.</p>

      <h2 id="11">11. Communications</h2>
      <p>We may send transactional communications related to:</p>
      <ul>
        <li>Billing</li>
        <li>Renewal notices</li>
        <li>Payment confirmations</li>
        <li>Account changes</li>
      </ul>
      <p>These are not marketing communications and are necessary for service administration.</p>
      <p>Marketing communications require separate consent and can be managed in your account settings.</p>

      <h2 id="12">12. Contact</h2>
      <p>Questions regarding subscriptions:</p>
      <p><a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>
      <p>
        {LEGAL_COMPANY_NAME}<br />
        {LEGAL_ADDRESS.line1}<br />
        {LEGAL_ADDRESS.city}<br />
        {LEGAL_ADDRESS.country}
      </p>
    </LegalPageShell>
  );
}
