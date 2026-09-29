import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';
import Link from 'next/link';

const SECTIONS = [
  {
    title: '1. What We Collect',
    body: `When you create an account, we store your email address, an optional name and an argon2id hash of your password. When you use the chat, we store your messages and the AI's responses to provide conversation history. When you upload documents, we store the file and processed text chunks to power personalised retrieval.`,
  },
  {
    title: '2. What We Do Not Collect',
    body: `We do not collect precise location or financial information. Aadhaar and phone numbers found in uploaded reports are masked before any AI model sees the text. We do not collect data from third-party sources about you. We do not use tracking pixels or cross-site tracking cookies.`,
  },
  {
    title: '3. How We Use Your Data',
    body: `Your data is used exclusively to operate the Service: to authenticate you, to retrieve relevant context for your queries, and to maintain conversation history. We do not use your health data to train or fine-tune any AI model. We do not sell, rent, or share your data with third parties for marketing purposes.`,
  },
  {
    title: '4. Data Processors',
    body: `One sub-processor: DeepSeek (AI models for understanding, retrieval, answering and a post-hoc safety audit), whose API servers are outside India. Chat messages and masked report text are sent to it. Public medical sources (PubMed, MedlinePlus, NLM) receive search terms, never your identity or your reports. This is a demo that uses synthetic data only; with real users each processor would need an agreement and a cross-border transfer review.`,
  },
  {
    title: '5. Data Retention',
    body: `Your conversation history and uploaded documents are retained as long as your account is active. You may delete individual conversations or documents at any time from the dashboard, or delete your whole account from the Account page, which removes every conversation, document, extracted value and file. The security audit log is kept for one year with your identity replaced by a pseudonym.`,
  },
  {
    title: '6. Your Rights',
    body: `You can see your conversations and documents in the dashboard, download any document you uploaded, and erase your account and everything in it yourself from the Account page.`,
  },
  {
    title: '7. Cookies',
    body: `Etheria uses one essential cookie: an httpOnly refresh-token cookie that keeps you signed in. Display preferences are kept in your browser's local storage. We do not use advertising or analytics cookies.`,
  },
  {
    title: '8. Children',
    body: `The Service is not directed to children under 18. We do not knowingly collect data from minors. If you believe a minor has created an account, contact us and we will promptly delete it.`,
  },
  {
    title: '9. Security',
    body: `Uploaded files are encrypted at rest with AES-256-GCM. Every data endpoint requires authentication, and Postgres row-level security scopes each user's rows to that user. See our Security page for a full breakdown.`,
  },
  {
    title: '10. International Transfers',
    body: `The data store runs on the operator's machine. Chat messages and masked report text are processed by DeepSeek's API servers outside India. By using this demo you agree to that transfer; use synthetic data only.`,
  },
  {
    title: '11. Changes to This Policy',
    body: `We may update this Privacy Policy periodically. Material changes will be communicated via email or in-app notice at least 14 days before taking effect.`,
  },
  {
    title: '12. Contact',
    body: `Privacy questions, data subject requests, or concerns can be sent to privacy@etheria.health. We aim to respond within 5 business days.`,
  },
];

export default function PrivacyPage() {
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
            Privacy
            <br />
            <span className="italic">Policy.</span>
          </h1>
          <p className="mt-6 font-sans text-[13px] text-cream/40">Last updated: April 12, 2026</p>
        </div>
      </section>

      {/* CONTENT */}
      <section className="bg-[#f0ede6] py-16 md:py-24 px-6 md:px-14 lg:px-24">
        <div className="max-w-[760px] mx-auto flex flex-col gap-10">
          <p className="font-sans text-[14px] text-muted-text leading-[1.8]">
            Etheria is built on the principle that your health data belongs to you. This Privacy
            Policy explains what we collect, why we collect it, and how you can control it.
          </p>

          {SECTIONS.map((s) => (
            <div key={s.title} className="flex flex-col gap-3">
              <h2 className="font-serif text-[20px] text-dark-text font-light">{s.title}</h2>
              <p className="font-sans text-[14px] text-muted-text leading-[1.8]">{s.body}</p>
            </div>
          ))}

          <div className="pt-6 border-t border-black/[0.06] flex gap-4">
            <Link href="/terms" className="font-sans text-[13px] text-[#2ebd55] hover:underline">
              Terms of Use →
            </Link>
            <Link
              href="/security"
              className="font-sans text-[13px] text-muted-text hover:text-dark-text transition-colors"
            >
              Security overview
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
