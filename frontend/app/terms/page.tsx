import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';
import Link from 'next/link';

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: `By accessing or using Etheria ("the Service"), you agree to be bound by these Terms of Use. If you do not agree, do not use the Service. Etheria is operated by Cybersprinter ("we", "us", "our").`,
  },
  {
    title: '2. Nature of the Service',
    body: `Etheria is an educational health information tool. It is not a licensed medical device, does not provide medical advice, and does not establish a doctor-patient relationship. Information provided by Etheria is for educational and informational purposes only. You should always consult a qualified healthcare professional before making any health-related decisions.`,
  },
  {
    title: '3. Eligibility',
    body: `You must be at least 18 years old to create an account. By using the Service, you represent that you meet this requirement and that the information you provide during registration is accurate and complete.`,
  },
  {
    title: '4. Prohibited Uses',
    body: `You may not use the Service to: (a) attempt to circumvent safety measures; (b) upload malicious files or content; (c) impersonate another person; (d) violate any applicable law or regulation; (e) use automated means to access the Service beyond normal personal use; or (f) attempt to extract or reverse-engineer the underlying models or retrieval systems.`,
  },
  {
    title: '5. User Content',
    body: `Content you upload (documents, chat messages) remains yours. By uploading, you grant Etheria a limited licence to process that content solely to provide the Service to you. We do not use your health data to train AI models.`,
  },
  {
    title: '6. Intellectual Property',
    body: `All software, design, text, graphics, and other content comprising the Etheria platform are the intellectual property of Cybersprinter or its licensors. You may not copy, modify, distribute, or create derivative works without our express written consent.`,
  },
  {
    title: '7. Disclaimers',
    body: `The Service is provided "as is" without warranties of any kind. We do not warrant that the Service will be uninterrupted, error-free, or that the information it provides is medically accurate or complete. We expressly disclaim all liability for any health decisions made based on Etheria's output.`,
  },
  {
    title: '8. Limitation of Liability',
    body: `To the maximum extent permitted by law, Cybersprinter will not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of the Service, even if advised of the possibility of such damages.`,
  },
  {
    title: '9. Termination',
    body: `We reserve the right to suspend or terminate your access to the Service at any time for violations of these Terms or for any other reason at our discretion. You may delete your account at any time from the dashboard.`,
  },
  {
    title: '10. Governing Law',
    body: `These Terms are governed by the laws of the jurisdiction in which Cybersprinter operates, without regard to conflict of law principles. Any disputes arising from these Terms will be resolved in the applicable courts of that jurisdiction.`,
  },
  {
    title: '11. Changes to Terms',
    body: `We may update these Terms from time to time. Material changes will be communicated via the email address associated with your account or via an in-app notice. Continued use of the Service after changes take effect constitutes acceptance.`,
  },
  {
    title: '12. Contact',
    body: `For questions about these Terms, contact us at legal@etheria.health.`,
  },
];

export default function TermsPage() {
  return (
    <>
      <Header />

      {/* HERO */}
      <section className="relative w-full bg-[#162a1c] flex flex-col justify-end px-6 md:px-14 lg:px-24 pt-36 pb-14">
        <div className="relative z-10 max-w-[900px]">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-6 block">
            Legal
          </span>
          <h1 className="font-flare text-[clamp(40px,6vw,90px)] font-normal leading-[0.92] text-cream tracking-[-0.03em] uppercase">
            Terms of
            <br />
            <span className="italic">Use.</span>
          </h1>
          <p className="mt-6 font-sans text-[13px] text-cream/40">Last updated: April 12, 2026</p>
        </div>
      </section>

      {/* CONTENT */}
      <section className="bg-[#f0ede6] py-16 md:py-24 px-6 md:px-14 lg:px-24">
        <div className="max-w-[760px] mx-auto flex flex-col gap-10">
          <div className="font-sans text-[14px] text-muted-text leading-[1.75] p-6 bg-amber-50 border border-amber-200 rounded-2xl">
            <strong className="text-dark-text">Important:</strong> Etheria does not provide medical
            advice. It is an educational tool only. Always consult a qualified healthcare
            professional for medical decisions.
          </div>

          {SECTIONS.map((s) => (
            <div key={s.title} className="flex flex-col gap-3">
              <h2 className="font-serif text-[20px] text-dark-text font-light">{s.title}</h2>
              <p className="font-sans text-[14px] text-muted-text leading-[1.8]">{s.body}</p>
            </div>
          ))}

          <div className="pt-6 border-t border-black/[0.06] flex gap-4">
            <Link href="/privacy" className="font-sans text-[13px] text-[#2ebd55] hover:underline">
              Privacy Policy →
            </Link>
            <Link
              href="/contact"
              className="font-sans text-[13px] text-muted-text hover:text-dark-text transition-colors"
            >
              Contact us
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
