import LegalPageShell from "../_LegalPageShell";
import { LEGAL_COMPANY_NAME, LEGAL_ADDRESS, LEGAL_EMAIL_SUPPORT } from "../_legalMeta";

export default function Page() {
  return (
    <LegalPageShell doc="disclaimer" title="Disclaimer">
      <p>
        <strong>Regime Intelligence / {LEGAL_COMPANY_NAME}</strong>
      </p>

      <h2 id="1">1. No Investment, Financial, Tax, Legal or Other Professional Advice</h2>
      <p>
        The information provided by Regime Intelligence (the “Service”) — including content, tools, analysis, data, research, models, alerts, commentary, or any other materials — is for educational and informational purposes only and does not constitute:
      </p>
      <ul>
        <li>investment advice,</li>
        <li>financial planning advice,</li>
        <li>tax advice,</li>
        <li>legal advice,</li>
        <li>accounting advice,</li>
        <li>or professional advice of any kind.</li>
      </ul>
      <p>
        You should not interpret anything on or through the Service as a recommendation to buy, sell, hold, or otherwise transact in any financial instrument, security, investment strategy, or market.
      </p>

      <h2 id="2">2. No Solicitation or Endorsement</h2>
      <p>
        Nothing in the Service is intended to solicit investments or trade activity in any jurisdiction. The Service does not endorse or recommend any particular security, asset, strategy, facilitator (brokerage, exchange, advisor), or execution method.
      </p>

      <h2 id="3">3. Educational Purposes Only</h2>
      <p>
        Any content, commentary, or analysis offered by the Service is intended solely to support your understanding of market regimes, historical context, and analytic frameworks. Such content is not tailored to your personal financial situation, risk tolerance, objectives, or needs.
      </p>

      <h2 id="4">4. You Are Responsible for Your Decisions</h2>
      <p>
        You are solely responsible for any decisions you make based on information obtained through the Service. You should conduct your own research and, if appropriate, seek the advice of a qualified professional before making any financial, tax, legal, or investment decisions.
      </p>

      <h2 id="5">5. No Warranty</h2>
      <p>
        While we strive for accuracy, completeness, and timeliness, the Service and its content are provided “as is” without warranty of any kind, whether express or implied, including but not limited to:
      </p>
      <ul>
        <li>accuracy,</li>
        <li>fitness for a particular purpose,</li>
        <li>completeness,</li>
        <li>non-infringement,</li>
        <li>or suitability for your specific needs.</li>
      </ul>

      <h2 id="6">6. Third-Party Information</h2>
      <p>
        Third-party data or content made available through the Service (including news, research, or external links) is provided for convenience and general informational purposes only. We do not guarantee the accuracy, completeness, or reliability of third-party information and we are not responsible for any losses or damages arising from its use.
      </p>

      <h2 id="7">7. No Liability for Losses</h2>
      <p>
        To the maximum extent permitted by applicable law, {LEGAL_COMPANY_NAME} and its affiliates, officers, directors, employees, contractors, or agents are not liable for any loss or damage arising directly or indirectly from:
      </p>
      <ul>
        <li>your access to or use of the Service,</li>
        <li>reliance on any content,</li>
        <li>any errors or omissions in the Service,</li>
        <li>delays or interruptions in delivery,</li>
        <li>or any actions you take or fail to take.</li>
      </ul>
      <p>You expressly acknowledge and agree that your use of the Service is at your sole risk.</p>

      <h2 id="8">8. Jurisdictional Issues</h2>
      <p>
        Laws and regulations regarding financial services, investments, and digital platforms vary by jurisdiction. The Service is not intended to subject {LEGAL_COMPANY_NAME} to regulation in any jurisdiction where Logos is not licensed to provide such services.
      </p>
      <p>
        If you access the Service from outside Canada, you are responsible for compliance with local laws. Nothing in this Disclaimer modifies or limits the application of a jurisdiction’s prohibitions or requirements.
      </p>

      <h2 id="9">9. Agreement</h2>
      <p>
        By using the Service, you acknowledge that you have read, understood, and agree to this Disclaimer and that it forms part of your agreement with {LEGAL_COMPANY_NAME} regarding use of the Service.
      </p>

      <h2 id="10">10. Contact</h2>
      <p>For questions about this Disclaimer:</p>
      <p>Email: <a href={`mailto:${LEGAL_EMAIL_SUPPORT}`}>{LEGAL_EMAIL_SUPPORT}</a></p>
      <p>
        Address:<br />
        {LEGAL_COMPANY_NAME}<br />
        {LEGAL_ADDRESS.line1}<br />
        {LEGAL_ADDRESS.city}<br />
        {LEGAL_ADDRESS.country}
      </p>
    </LegalPageShell>
  );
}
