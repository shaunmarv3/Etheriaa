import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';
import Link from 'next/link';

const SOURCES = [
  {
    tag: 'Knowledge Graph',
    title: 'Curated India-common conditions',
    description:
      'A Neo4j graph of India-common conditions and their symptoms, each entry carrying a cited source. The assistant ranks conditions by how well your symptoms cover them, and says so when a question falls outside the graph.',
    badge: 'Neo4j',
  },
  {
    tag: 'Drug Interactions',
    title: 'DDInter + a curated safety net',
    description:
      'Drug pairs are checked against DDInter, backed by a curated list of critical interactions. A pair that is not found is reported as "not found, confirm with a pharmacist", never as safe.',
    badge: 'DDInter',
  },
  {
    tag: 'Indian Medicines',
    title: 'Brand names to ingredients',
    description:
      '253,973 Indian brand names are matched (fuzzy, trigram) to their ingredients, so "Dolo 650" resolves to paracetamol (acetaminophen). Ingredient names are normalised with RxNav.',
    badge: 'NLM RxNav',
  },
  {
    tag: 'Literature',
    title: 'PubMed',
    description:
      "The National Library of Medicine's index of biomedical literature, searched when a question needs published evidence. Results are reranked by a cross-encoder before they are used.",
    badge: 'NIH',
  },
  {
    tag: 'Patient Information',
    title: 'MedlinePlus',
    description:
      'Plain-language health topics from MedlinePlus, a National Library of Medicine service for the general public.',
    badge: 'NLM',
  },
  {
    tag: 'Your Reports',
    title: 'Your own lab reports',
    description:
      'Values extracted from reports you upload. Every stored number must appear verbatim in the source text, and high/low flags are computed by code against the printed reference range.',
    badge: 'Private',
  },
];

const PIPELINE = [
  {
    step: '01',
    label: 'Input guard',
    detail:
      'Rule-based checks run first: red-flag symptoms, self-harm phrases and injection attempts are caught before any model is called.',
  },
  {
    step: '02',
    label: 'Understanding',
    detail:
      'A DeepSeek model reads the message into a structured form: intent, symptoms, medicines mentioned.',
  },
  {
    step: '03',
    label: 'Retrieval and triage, in parallel',
    detail:
      'A bounded tool-calling agent picks from 8 read-only tools (your labs, medicines and reports; the graph; interactions; PubMed; MedlinePlus). Triage runs alongside it; rules can only raise the level.',
  },
  {
    step: '04',
    label: 'Reranking',
    detail: 'The evidence gathered is reranked by a cross-encoder model.',
  },
  {
    step: '05',
    label: 'Answer, streamed and filtered',
    detail:
      'The reply streams sentence by sentence through a deterministic filter that blocks diagnoses and doses. For RED triage, the emergency block (112, 108, Tele-MANAS 14416) is sent before any model text.',
  },
  {
    step: '06',
    label: 'Audit',
    detail:
      'After the reply, a second model audits it against the safety rules. The audit is for measurement; it never blocks the answer.',
  },
];

export default function KnowledgeBasePage() {
  return (
    <>
      <Header />

      {/* HERO */}
      <section className="relative w-full min-h-[55vh] bg-[#162a1c] flex flex-col justify-end px-6 md:px-14 lg:px-24 pt-36 pb-14 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute bottom-0 left-1/4 w-[60vw] h-[50vw] max-w-[700px] rounded-full bg-[radial-gradient(circle,_rgba(68,199,103,0.14)_0%,_transparent_65%)] blur-[100px]" />
        </div>
        <div className="relative z-10 max-w-[900px]">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-6 block">
            Knowledge Base
          </span>
          <h1 className="font-flare text-[clamp(48px,8vw,110px)] font-normal leading-[0.9] text-cream tracking-[-0.03em] uppercase">
            Medical
            <br />
            <span className="italic">Intelligence.</span>
          </h1>
          <p className="mt-8 font-sans text-[15px] text-cream/55 font-light leading-[1.75] max-w-[480px]">
            Etheria draws from a curated stack of authoritative medical databases and peer-reviewed
            literature — not the open web.
          </p>
        </div>
      </section>

      {/* SOURCES */}
      <section className="bg-[#f0ede6] py-20 md:py-28 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex flex-col md:flex-row gap-10 md:gap-20 items-start mb-16">
            <div className="shrink-0">
              <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-3">
                Data Sources
              </span>
              <div className="w-8 h-px bg-[#2ebd55]" />
            </div>
            <p className="font-serif text-[clamp(18px,2.5vw,26px)] font-normal leading-[1.5] text-dark-text max-w-[600px]">
              Every piece of information Etheria retrieves originates from a recognised medical
              authority — no user-generated content, no unvetted web results.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {SOURCES.map((s) => (
              <div
                key={s.title}
                className="bg-white rounded-2xl p-7 flex flex-col gap-3 border border-black/[0.05]"
              >
                <div className="flex items-center justify-between">
                  <span className="font-sans text-[10px] tracking-[0.18em] uppercase text-[#2ebd55]">
                    {s.tag}
                  </span>
                  <span className="font-sans text-[10px] bg-[#162a1c]/8 text-[#162a1c]/60 px-2 py-0.5 rounded-full border border-[#162a1c]/10">
                    {s.badge}
                  </span>
                </div>
                <h3 className="font-serif text-[20px] text-dark-text font-light leading-[1.3]">
                  {s.title}
                </h3>
                <p className="font-sans text-[13px] text-muted-text leading-[1.75]">
                  {s.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PIPELINE */}
      <section className="bg-white py-20 md:py-28 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-14">
            How a query flows through Etheria
          </span>
          <div className="flex flex-col gap-0">
            {PIPELINE.map((p, i) => (
              <div
                key={p.step}
                className={`flex gap-8 md:gap-14 items-start py-8 ${i < PIPELINE.length - 1 ? 'border-b border-black/[0.06]' : ''}`}
              >
                <span className="font-sans text-[11px] text-muted-text/50 tracking-widest shrink-0 w-7 pt-0.5">
                  {p.step}
                </span>
                <div className="flex flex-col md:flex-row md:items-start gap-2 md:gap-12 flex-1">
                  <h4 className="font-serif text-[18px] text-dark-text font-light leading-tight md:w-[220px] shrink-0">
                    {p.label}
                  </h4>
                  <p className="font-sans text-[13px] text-muted-text leading-[1.75]">{p.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* DISCLAIMER */}
      <section className="bg-[#162a1c] py-14 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto flex flex-col md:flex-row items-start md:items-center gap-6 justify-between">
          <p className="font-sans text-[13px] text-cream/50 leading-[1.7] max-w-[560px]">
            Etheria is an educational health guidance tool, not a licensed medical device. It does
            not provide diagnoses, prescribe treatments, or replace professional clinical judgement.
            Always consult a qualified healthcare provider.
          </p>
          <Link
            href="/research"
            className="shrink-0 border border-cream/25 text-cream font-sans text-[13px] font-medium py-3 px-7 rounded-full hover:border-cream/60 hover:bg-white/5 transition-all"
          >
            View research citations →
          </Link>
        </div>
      </section>

      <Footer />
    </>
  );
}
