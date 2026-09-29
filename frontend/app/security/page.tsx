import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';

const PILLARS = [
  {
    tag: '01 — Encryption',
    title: 'Encrypted files at rest',
    body: 'Uploaded reports are encrypted with AES-256-GCM before they touch disk, under random storage names. Database volumes rely on disk encryption where deployed; this demo runs locally.',
  },
  {
    tag: '02 — Authentication',
    title: 'Rotating sessions',
    body: 'Passwords are hashed with argon2id. Access tokens are 15-minute JWTs kept in memory, never in localStorage. Refresh tokens rotate on every use, and reusing an old one revokes the whole session.',
  },
  {
    tag: '03 — Data isolation',
    title: 'Row-level security',
    body: 'Postgres row-level security scopes every user table to the signed-in user, on top of per-user service checks. The AI assistant reads your identity from trusted server context, never from model output.',
  },
  {
    tag: '04 — PII masking',
    title: 'Masked before any model',
    body: 'Aadhaar numbers and Indian phone numbers are masked in report text before any AI model sees it and before anything is indexed. Uploaded reports are treated as data, never as instructions.',
  },
  {
    tag: '05 — Abuse limits',
    title: 'Rate limits and upload checks',
    body: 'Chat is limited to 20 messages a minute, uploads to 10 an hour, sign-in and sign-up to 5 a minute. Uploads are typed by their bytes and capped at 10 MB and 30 pages.',
  },
  {
    tag: '06 — Erasure',
    title: 'Delete anything, any time',
    body: 'Delete a conversation, a document or your whole account from the dashboard. Account deletion removes every row, file and chat checkpoint; the audit log keeps a pseudonymous entry, with no health content, for one year.',
  },
];

export default function SecurityPage() {
  return (
    <>
      <Header />

      {/* HERO */}
      <section className="relative w-full min-h-[55vh] bg-[#162a1c] flex flex-col justify-end px-6 md:px-14 lg:px-24 pt-36 pb-14 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-10%] right-0 w-[60vw] h-[60vw] max-w-[700px] rounded-full bg-[radial-gradient(circle,_rgba(68,199,103,0.15)_0%,_transparent_65%)] blur-[100px]" />
        </div>
        <div className="relative z-10 max-w-[900px]">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-6 block">
            Trust & Security
          </span>
          <h1 className="font-flare text-[clamp(48px,8vw,110px)] font-normal leading-[0.9] text-cream tracking-[-0.03em] uppercase">
            Built
            <br />
            <span className="italic">Secure.</span>
          </h1>
          <p className="mt-8 font-sans text-[15px] text-cream/55 font-light leading-[1.75] max-w-[480px]">
            Health data is among the most sensitive information that exists. We treat security as a
            product requirement, not an afterthought.
          </p>
        </div>
      </section>

      {/* PILLARS GRID */}
      <section className="bg-[#f0ede6] py-20 md:py-28 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex flex-col md:flex-row gap-10 md:gap-20 items-start mb-16">
            <div className="shrink-0">
              <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-3">
                Security Model
              </span>
              <div className="w-8 h-px bg-[#2ebd55]" />
            </div>
            <p className="font-serif text-[clamp(18px,2.5vw,26px)] font-normal leading-[1.5] text-dark-text max-w-[600px]">
              Every layer of the Etheria stack — from how you authenticate to how your data is
              stored and deleted — is designed around the principle of least privilege.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-black/[0.06] border border-black/[0.06] rounded-2xl overflow-hidden">
            {PILLARS.map((p) => (
              <div key={p.tag} className="bg-[#f0ede6] p-8 flex flex-col gap-4">
                <span className="font-sans text-[10px] tracking-[0.18em] uppercase text-[#2ebd55]">
                  {p.tag}
                </span>
                <h3 className="font-serif text-[20px] text-dark-text font-light leading-[1.3]">
                  {p.title}
                </h3>
                <p className="font-sans text-[13px] text-muted-text leading-[1.75]">{p.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* COMPLIANCE */}
      <section className="bg-white py-20 md:py-24 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-10">
            Controls
          </span>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { label: 'argon2id', note: 'Password hashing' },
              { label: 'RLS', note: 'Postgres row-level security' },
              { label: 'AES-GCM', note: '256-bit, files at rest' },
              { label: 'DPDP', note: 'Designed to the 2025 Rules, not certified' },
            ].map(({ label, note }) => (
              <div
                key={label}
                className="border border-black/[0.07] rounded-2xl p-6 flex flex-col gap-2"
              >
                <span className="font-flare text-[28px] text-[#162a1c] leading-none">{label}</span>
                <span className="font-sans text-[12px] text-muted-text">{note}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* RESPONSIBLE DISCLOSURE */}
      <section className="bg-[#162a1c] py-16 md:py-20 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto flex flex-col md:flex-row items-center justify-between gap-8">
          <div>
            <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 block mb-3">
              Responsible Disclosure
            </span>
            <h2 className="font-serif text-[clamp(20px,3vw,30px)] text-cream font-light leading-[1.3] max-w-[500px]">
              Found a vulnerability? This is a portfolio project with synthetic data only; please
              open an issue on GitHub.
            </h2>
          </div>
          <a
            href="https://github.com/shaunmarv3/etheria-v2/issues"
            className="shrink-0 bg-[#44c767] text-white font-sans text-[14px] font-medium py-3.5 px-8 rounded-full tracking-[0.02em] transition-all hover:bg-[#3ab55a] hover:-translate-y-0.5 whitespace-nowrap"
          >
            Open an issue
          </a>
        </div>
      </section>

      <Footer />
    </>
  );
}
