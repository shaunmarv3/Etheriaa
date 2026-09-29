import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';
import Link from 'next/link';

const PAPERS = [
  {
    category: 'Clinical Decision Support',
    title:
      'Artificial intelligence in clinical decision support: challenges for evaluating AI and practical implications',
    authors: 'Sutton RT, Pincock D, Baumgart DC, et al.',
    journal: 'The Lancet Digital Health',
    year: '2020',
    doi: '10.1016/S2589-7500(19)30190-4',
  },
  {
    category: 'Large Language Models in Medicine',
    title: 'Large language models encode clinical knowledge',
    authors: 'Singhal K, Azizi S, Tu T, et al.',
    journal: 'Nature',
    year: '2023',
    doi: '10.1038/s41586-023-06291-2',
  },
  {
    category: 'Retrieval-Augmented Generation',
    title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
    authors: 'Lewis P, Perez E, Piktus A, et al.',
    journal: 'Advances in Neural Information Processing Systems (NeurIPS)',
    year: '2020',
    doi: '10.48550/arXiv.2005.11401',
  },
  {
    category: 'Medical Triage',
    title: 'Electronic triage systems in emergency medicine: a systematic review',
    authors: 'Zachariasse JM, van der Hagen V, Seiger N, et al.',
    journal: 'Emergency Medicine Journal',
    year: '2019',
    doi: '10.1136/emermed-2018-208307',
  },
  {
    category: 'Biomedical NLP',
    title: 'scispaCy: Fast and Robust Models for Biomedical Natural Language Processing',
    authors: 'Neumann M, King D, Beltagy I, Ammar W.',
    journal: 'Proceedings of the 18th BioNLP Workshop',
    year: '2019',
    doi: '10.18653/v1/W19-5034',
  },
  {
    category: 'Knowledge Graphs in Healthcare',
    title:
      'A review of biomedical datasets relating to drug discovery: a knowledge graph perspective',
    authors: 'Bonner S, Barrett IP, Ye C, et al.',
    journal: 'Briefings in Bioinformatics',
    year: '2022',
    doi: '10.1093/bib/bbac404',
  },
  {
    category: 'Differential Diagnosis AI',
    title:
      'An AI system for diagnosing age-related macular degeneration and diabetic macular edema',
    authors: 'Keenan TD, Dharssi S, Peng Y, et al.',
    journal: 'Ophthalmology',
    year: '2021',
    doi: '10.1016/j.ophtha.2021.04.006',
  },
  {
    category: 'Patient Safety',
    title: 'Chatbots as medical advice tools: evaluation of accuracy and safety',
    authors: 'Laranjo L, Dunn AG, Tong HL, et al.',
    journal: 'npj Digital Medicine',
    year: '2023',
    doi: '10.1038/s41746-023-00979-5',
  },
];

export default function ResearchPage() {
  return (
    <>
      <Header />

      {/* HERO */}
      <section className="relative w-full min-h-[50vh] bg-[#162a1c] flex flex-col justify-end px-6 md:px-14 lg:px-24 pt-36 pb-14 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 right-1/4 w-[50vw] h-[50vw] max-w-[600px] rounded-full bg-[radial-gradient(circle,_rgba(68,199,103,0.13)_0%,_transparent_65%)] blur-[90px]" />
        </div>
        <div className="relative z-10 max-w-[900px]">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-6 block">
            Research & References
          </span>
          <h1 className="font-flare text-[clamp(48px,8vw,110px)] font-normal leading-[0.9] text-cream tracking-[-0.03em] uppercase">
            Grounded
            <br />
            <span className="italic">in Evidence.</span>
          </h1>
          <p className="mt-8 font-sans text-[15px] text-cream/55 font-light leading-[1.75] max-w-[480px]">
            The clinical reasoning, retrieval methods, and safety mechanisms in Etheria are informed
            by peer-reviewed research.
          </p>
        </div>
      </section>

      {/* PAPERS */}
      <section className="bg-[#f0ede6] py-20 md:py-28 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-12">
            Referenced literature
          </span>

          <div className="flex flex-col gap-0">
            {PAPERS.map((p, i) => (
              <div
                key={i}
                className={`py-8 ${i < PAPERS.length - 1 ? 'border-b border-black/[0.06]' : ''}`}
              >
                <div className="flex flex-col md:flex-row md:items-start gap-4 md:gap-12">
                  <span className="font-sans text-[10px] tracking-[0.15em] uppercase text-[#2ebd55] shrink-0 md:w-[180px] pt-1">
                    {p.category}
                  </span>
                  <div className="flex flex-col gap-1.5 flex-1">
                    <h3 className="font-serif text-[17px] text-dark-text font-light leading-[1.45]">
                      {p.title}
                    </h3>
                    <p className="font-sans text-[12px] text-muted-text">{p.authors}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="font-sans text-[11px] italic text-dark-text/60">
                        {p.journal}
                      </span>
                      <span className="text-dark-text/20">·</span>
                      <span className="font-sans text-[11px] text-dark-text/50">{p.year}</span>
                      <span className="text-dark-text/20">·</span>
                      <a
                        href={`https://doi.org/${p.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-sans text-[11px] text-[#2ebd55] hover:underline"
                      >
                        DOI →
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-white py-16 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <p className="font-serif text-[20px] text-dark-text font-light leading-[1.4] max-w-[480px]">
              Working on research involving AI in clinical settings?
            </p>
            <p className="mt-2 font-sans text-[13px] text-muted-text">
              We actively welcome academic and clinical research collaborations.
            </p>
          </div>
          <Link
            href="/contact"
            className="shrink-0 bg-[#162a1c] text-[#44c767] font-sans text-[14px] font-medium py-3.5 px-8 rounded-full hover:bg-[#1f3826] transition-all"
          >
            Get in touch
          </Link>
        </div>
      </section>

      <Footer />
    </>
  );
}
