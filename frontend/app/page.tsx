'use client';

import { useRef, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../src/lib/auth';
import Image from 'next/image';
import Header from '../src/components/Header';
import Footer from '../src/components/Footer';

/* ─────────────────────────────────────────────────
   useInView — fires once when element enters viewport
───────────────────────────────────────────────── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, visible] as const;
}

/* ─────────────────────────────────────────────────
   Shared card transition style (can't use raw CSS
   `transition:` syntax inside Tailwind className)
───────────────────────────────────────────────── */
const cardTransition: React.CSSProperties = {
  transition:
    'transform 0.4s cubic-bezier(0.16,1,0.3,1), box-shadow 0.4s cubic-bezier(0.16,1,0.3,1), border-color 0.4s ease',
};

export default function Home() {
  const heroRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { isSignedIn } = useAuth();

  const handleStartAssessment = () => {
    router.push(isSignedIn ? '/dashboard' : '/sign-in');
  };

  const [taglineRef, taglineVisible] = useInView(0.2);
  const [featuresRef, featuresVisible] = useInView(0.1);
  const [worksRef, worksVisible] = useInView(0.1);
  const [ctaRef, ctaVisible] = useInView(0.2);

  return (
    <>
      <style>{`
        /* ── Incoming Character Animation ── */
        @keyframes charReveal {
          0% { opacity: 0; transform: translateY(60px) rotate(5deg) scale(0.9); filter: blur(15px); }
          100% { opacity: 1; transform: translateY(0) rotate(0) scale(1); filter: blur(0); }
        }
        .char-animate {
          display: inline-block;
          opacity: 0;
          animation: charReveal 1.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          will-change: transform, opacity, filter;
        }
        
        @keyframes fadeScale {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .hero-tagline {
          animation: fadeScale 1.4s cubic-bezier(0.16, 1, 0.3, 1) 1.2s both;
        }

        /* ── Premium Ambient Spotlight ── */
        @keyframes breathingGlow {
          0%, 100% { transform: scale(1) translate(-50%, -50%); opacity: 0.6; }
          50%      { transform: scale(1.08) translate(-48%, -48%); opacity: 0.9; }
        }
        .ambient-spotlight {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 90vw;
          height: 90vw;
          max-width: 1200px;
          max-height: 1200px;
          border-radius: 50%;
          background: radial-gradient(circle at center, rgba(68,199,103,0.3) 0%, rgba(26,92,74,0.15) 30%, transparent 65%);
          filter: blur(100px);
          animation: breathingGlow 14s ease-in-out infinite;
          transform: translate(-50%, -50%);
          pointer-events: none;
        }

        /* ── Scroll reveal ── */
        .reveal {
          opacity: 0;
          transform: translateY(32px);
          transition: opacity 0.75s cubic-bezier(0.16,1,0.3,1),
                      transform 0.75s cubic-bezier(0.16,1,0.3,1);
        }
        .reveal.in-view {
          opacity: 1;
          transform: translateY(0);
        }

        /* ── Staggered card children ── */
        .stagger-cards > * {
          opacity: 0;
          transform: translateY(28px);
          transition: opacity 0.65s cubic-bezier(0.16,1,0.3,1),
                      transform 0.65s cubic-bezier(0.16,1,0.3,1);
        }
        .stagger-cards.in-view > *:nth-child(1) { opacity:1; transform:translateY(0); transition-delay: 0.05s; }
        .stagger-cards.in-view > *:nth-child(2) { opacity:1; transform:translateY(0); transition-delay: 0.15s; }
        .stagger-cards.in-view > *:nth-child(3) { opacity:1; transform:translateY(0); transition-delay: 0.25s; }
        .stagger-cards.in-view > *:nth-child(4) { opacity:1; transform:translateY(0); transition-delay: 0.35s; }

        /* ── Feature card hover (dark cards) ── */
        .feature-card:hover {
          border-color: rgba(68,199,103,0.20);
          box-shadow: 0 20px 50px -12px rgba(0,0,0,0.35);
          transform: translateY(-3px);
        }

        /* ── Process card hover (white cards) ── */
        .process-card:hover {
          transform: translateY(-10px);
          box-shadow: 0 32px 64px -16px rgba(0,0,0,0.14);
        }
      `}</style>

      <Header />

      {/* ── HERO ── */}
      <section
        className="relative w-full min-h-screen flex flex-col justify-center overflow-hidden bg-[#0d1c13]"
        ref={heroRef}
      >
        {/* Supreme Quality Background Lighting (No blown out white pixels) */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="ambient-spotlight" />
        </div>

        {/* Hero headline — Original Giant Layout, Re-mastered */}
        <div className="relative z-10 w-full px-4 sm:px-8 md:px-16 lg:px-24 xl:px-32 mix-blend-plus-lighter">
          <h1 className="font-flare text-[clamp(50px,13vw,210px)] font-normal leading-[0.8] text-[#f4f1e1] tracking-[-0.04em] uppercase w-full">
            <span className="block text-left will-change-transform pb-2">
              {'INTELLIGENT'.split('').map((char, i) => (
                <span
                  key={`line1-${i}`}
                  className="char-animate"
                  style={{ animationDelay: `${0.1 + i * 0.04}s` }}
                >
                  {char}
                </span>
              ))}
            </span>
            <span className="block italic text-right mt-1 pr-0 md:pr-12 text-[#e5dfc9] will-change-transform">
              {'ASSESSMENT'.split('').map((char, i) => (
                <span
                  key={`line2-${i}`}
                  className="char-animate"
                  style={{ animationDelay: `${0.5 + i * 0.04}s` }}
                >
                  {char}
                </span>
              ))}
            </span>
          </h1>
        </div>

        {/* Hero tagline */}
        <p className="hero-tagline absolute bottom-12 sm:bottom-16 left-4 sm:left-8 md:left-24 lg:left-32 z-10 font-sans text-[13px] md:text-[15px] leading-[1.65] text-[#f4f1e1]/70 font-light max-w-[280px] md:max-w-[400px]">
          <span className="font-medium text-[#f4f1e1]/90">Interactive Symptom Assessment.</span>
          <br />
          Understand your symptoms and your own
          <br />
          lab reports, in plain language.
        </p>
      </section>

      {/* ── TAGLINE ── */}
      <section className="bg-warm-white py-[60px] md:py-[100px] px-6 md:px-12 text-center relative">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 max-w-[800px] h-px bg-gradient-to-r from-transparent via-black/10 to-transparent" />
        <div ref={taglineRef} className={`reveal ${taglineVisible ? 'in-view' : ''}`}>
          <p className="font-serif text-[clamp(28px,4vw,50px)] font-normal leading-[1.35] text-dark-text max-w-[900px] mx-auto">
            Empowering early health awareness with{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#2ebd55] to-[#1a5c4a] font-medium tracking-tight">
              AI-based symptom assessment
            </span>
            . We check what you describe and{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#2ebd55] to-[#1a5c4a] font-medium tracking-tight">
              your own reports
            </span>{' '}
            against curated medical sources to guide your next steps.
          </p>
        </div>
      </section>

      {/* ── PLATFORM FEATURES ── */}
      <section className="bg-warm-white py-16 md:py-20 px-6 md:px-12 relative">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-[1200px] h-px bg-gradient-to-r from-transparent via-black/10 to-transparent" />

        <div ref={featuresRef} className={`reveal ${featuresVisible ? 'in-view' : ''}`}>
          <p className="font-sans text-[11px] font-medium tracking-[0.18em] uppercase text-light-text mb-8">
            Platform Features
          </p>
          <p className="font-serif text-[clamp(20px,2.5vw,28px)] font-normal leading-[1.55] text-dark-text max-w-[900px] mb-16">
            It conducts intelligent follow-up questioning to better assess the severity and urgency
            of symptoms. Based on the analysis, the system provides safe preliminary health guidance
            and recommends appropriate next steps such as self-care or medical consultation.
          </p>
        </div>

        {/* Feature cards — staggered */}
        <div
          className={`stagger-cards grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 ${featuresVisible ? 'in-view' : ''}`}
        >
          {/* Your Reports */}
          <div
            className="feature-card group relative flex flex-col justify-between bg-[#162a1c] rounded-2xl px-7 pt-8 pb-7 overflow-hidden cursor-default border border-white/[0.06]"
            style={cardTransition}
          >
            <div
              className="absolute top-0 left-0 w-full h-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
              style={{
                background:
                  'radial-gradient(ellipse at 30% 0%, rgba(68,199,103,0.12) 0%, transparent 65%)',
              }}
            />
            <div className="relative z-10 mb-8">
              <div className="w-10 h-10 rounded-xl bg-bright-green/10 border border-bright-green/20 flex items-center justify-center transition-colors duration-500 group-hover:bg-bright-green/20">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#44c767"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="8" y1="13" x2="16" y2="13" />
                  <line x1="8" y1="17" x2="13" y2="17" />
                </svg>
              </div>
            </div>
            <div className="relative z-10">
              <div className="font-flare text-[clamp(32px,4vw,48px)] font-normal text-cream leading-[0.95] tracking-[-0.02em] mb-5">
                Your
                <br />
                Reports
              </div>
              <div className="h-px w-full bg-white/[0.07] mb-5" />
              <p className="font-sans text-[13px] leading-[1.7] text-cream/45 font-light">
                Upload a lab report or prescription. Values are extracted, checked against the
                source text and flagged by code, then used to answer your questions.
              </p>
            </div>
          </div>

          {/* RAG Engine */}
          <div
            className="feature-card group relative flex flex-col justify-between bg-[#162a1c] rounded-2xl px-7 pt-8 pb-7 overflow-hidden cursor-default border border-white/[0.06]"
            style={cardTransition}
          >
            <div
              className="absolute top-0 left-0 w-full h-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
              style={{
                background:
                  'radial-gradient(ellipse at 30% 0%, rgba(68,199,103,0.12) 0%, transparent 65%)',
              }}
            />
            <div className="relative z-10 mb-8">
              <div className="w-10 h-10 rounded-xl bg-bright-green/10 border border-bright-green/20 flex items-center justify-center transition-colors duration-500 group-hover:bg-bright-green/20">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#44c767"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
              </div>
            </div>
            <div className="relative z-10">
              <div className="font-flare text-[clamp(32px,4vw,48px)] font-normal text-cream leading-[0.95] tracking-[-0.02em] mb-5">
                RAG
                <br />
                Engine
              </div>
              <div className="h-px w-full bg-white/[0.07] mb-5" />
              <p className="font-sans text-[13px] leading-[1.7] text-cream/45 font-light">
                Powered by dense retrieval-augmented generation grounded in trusted medical
                knowledge bases.
              </p>
            </div>
          </div>

          {/* Smart Follow-up */}
          <div
            className="feature-card group relative flex flex-col justify-between bg-[#162a1c] rounded-2xl px-7 pt-8 pb-7 overflow-hidden cursor-default border border-white/[0.06]"
            style={cardTransition}
          >
            <div
              className="absolute top-0 left-0 w-full h-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
              style={{
                background:
                  'radial-gradient(ellipse at 30% 0%, rgba(68,199,103,0.12) 0%, transparent 65%)',
              }}
            />
            <div className="relative z-10 mb-8">
              <div className="w-10 h-10 rounded-xl bg-bright-green/10 border border-bright-green/20 flex items-center justify-center transition-colors duration-500 group-hover:bg-bright-green/20">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#44c767"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
            </div>
            <div className="relative z-10">
              <div className="font-flare text-[clamp(32px,4vw,48px)] font-normal text-cream leading-[0.95] tracking-[-0.02em] mb-5">
                Smart
                <br />
                Follow-up
              </div>
              <div className="h-px w-full bg-white/[0.07] mb-5" />
              <p className="font-sans text-[13px] leading-[1.7] text-cream/45 font-light">
                Dynamically generates follow-up questions to isolate potential urgencies properly.
              </p>
            </div>
          </div>

          {/* Safe Guidance */}
          <div
            className="feature-card group relative flex flex-col justify-between bg-[#162a1c] rounded-2xl px-7 pt-8 pb-7 overflow-hidden cursor-default border border-white/[0.06]"
            style={cardTransition}
          >
            <div
              className="absolute top-0 left-0 w-full h-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
              style={{
                background:
                  'radial-gradient(ellipse at 30% 0%, rgba(68,199,103,0.12) 0%, transparent 65%)',
              }}
            />
            <div className="relative z-10 mb-8">
              <div className="w-10 h-10 rounded-xl bg-bright-green/10 border border-bright-green/20 flex items-center justify-center transition-colors duration-500 group-hover:bg-bright-green/20">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#44c767"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
            </div>
            <div className="relative z-10">
              <div className="font-flare text-[clamp(32px,4vw,48px)] font-normal text-cream leading-[0.95] tracking-[-0.02em] mb-5">
                Safe
                <br />
                Guidance
              </div>
              <div className="h-px w-full bg-white/[0.07] mb-5" />
              <p className="font-sans text-[13px] leading-[1.7] text-cream/45 font-light">
                Recommends safe next steps, reducing reliance on generic or unreliable online
                panic-searches.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── HOW ETHERIA WORKS ── */}
      <section
        id="how-it-works"
        className="bg-warm-white pb-24 md:pb-32 pt-16 md:pt-20 px-6 md:px-12 relative"
      >
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-[1200px] h-px bg-gradient-to-r from-transparent via-black/10 to-transparent" />

        <div ref={worksRef} className={`reveal ${worksVisible ? 'in-view' : ''}`}>
          <div className="flex justify-between items-start mb-12 gap-6 md:gap-10 flex-col md:flex-row">
            <p className="font-sans text-[11px] font-medium tracking-[0.18em] uppercase text-light-text w-full md:w-auto">
              How Etheria Works
            </p>
            <p className="font-serif text-[16px] md:text-[clamp(16px,2vw,20px)] font-normal text-muted-text w-full md:max-w-[420px] leading-[1.6]">
              By reducing reliance on unreliable online information, the solution aims to improve
              early health awareness.
            </p>
          </div>
        </div>

        {/* Process cards — staggered */}
        <div
          className={`stagger-cards grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 ${worksVisible ? 'in-view' : ''}`}
        >
          {/* Card 1 — Describe */}
          <div
            className="process-card relative flex flex-col group cursor-pointer bg-white rounded-2xl overflow-hidden border border-black/[0.07] shadow-[0_2px_16px_-6px_rgba(0,0,0,0.08)]"
            style={cardTransition}
          >
            <span
              aria-hidden="true"
              className="absolute bottom-[-6px] right-3 z-0 select-none pointer-events-none font-flare text-[108px] leading-none text-black/[0.04] transition-colors duration-500 group-hover:text-[#44c767]/[0.08]"
            >
              01
            </span>
            <div className="overflow-hidden aspect-[3/4] relative">
              <Image
                src="/speech_health.png"
                alt="Describe symptoms"
                fill
                className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    'linear-gradient(to top, #ffffff 0%, rgba(255,255,255,0.08) 42%, transparent 60%)',
                }}
              />
            </div>
            <div className="relative z-10 px-6 pt-2 pb-7 flex flex-col">
              <span className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-3">
                Chat
              </span>
              <h3 className="font-flare text-[28px] font-normal text-dark-text leading-[1.05] tracking-[-0.02em] mb-3">
                Describe
              </h3>
              <p className="font-sans text-[13px] leading-[1.7] text-light-text font-light mb-5">
                Type your symptoms in your own words. Etheria asks follow-up questions and checks
                for red flags first.
              </p>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-black/[0.07]" />
                <span className="text-bright-green text-[15px] transition-transform duration-300 group-hover:translate-x-1.5 inline-block">
                  →
                </span>
              </div>
            </div>
          </div>

          {/* Card 2 — Interact */}
          <div
            className="process-card relative flex flex-col group cursor-pointer bg-white rounded-2xl overflow-hidden border border-black/[0.07] shadow-[0_2px_16px_-6px_rgba(0,0,0,0.08)]"
            style={cardTransition}
          >
            <span
              aria-hidden="true"
              className="absolute bottom-[-6px] right-3 z-0 select-none pointer-events-none font-flare text-[108px] leading-none text-black/[0.04] transition-colors duration-500 group-hover:text-[#44c767]/[0.08]"
            >
              02
            </span>
            <div className="overflow-hidden aspect-[3/4] relative">
              <Image
                src="/symtoms.png"
                alt="Interact with follow-up questions"
                fill
                className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    'linear-gradient(to top, #ffffff 0%, rgba(255,255,255,0.08) 42%, transparent 60%)',
                }}
              />
            </div>
            <div className="relative z-10 px-6 pt-2 pb-7 flex flex-col">
              <span className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-3">
                Follow-up
              </span>
              <h3 className="font-flare text-[28px] font-normal text-dark-text leading-[1.05] tracking-[-0.02em] mb-3">
                Interact
              </h3>
              <p className="font-sans text-[13px] leading-[1.7] text-light-text font-light mb-5">
                Answer intelligent follow-up questions tailored to assess the severity of your
                inputs.
              </p>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-black/[0.07]" />
                <span className="text-bright-green text-[15px] transition-transform duration-300 group-hover:translate-x-1.5 inline-block">
                  →
                </span>
              </div>
            </div>
          </div>

          {/* Card 3 — Analyze */}
          <div
            className="process-card relative flex flex-col group cursor-pointer bg-white rounded-2xl overflow-hidden border border-black/[0.07] shadow-[0_2px_16px_-6px_rgba(0,0,0,0.08)]"
            style={cardTransition}
          >
            <span
              aria-hidden="true"
              className="absolute bottom-[-6px] right-3 z-0 select-none pointer-events-none font-flare text-[108px] leading-none text-black/[0.04] transition-colors duration-500 group-hover:text-[#44c767]/[0.08]"
            >
              03
            </span>
            <div className="overflow-hidden aspect-[3/4] relative">
              <Image
                src="/rag_analysis.png"
                alt="RAG Analysis"
                fill
                className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    'linear-gradient(to top, #ffffff 0%, rgba(255,255,255,0.08) 42%, transparent 60%)',
                }}
              />
            </div>
            <div className="relative z-10 px-6 pt-2 pb-7 flex flex-col">
              <span className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-3">
                RAG Analysis
              </span>
              <h3 className="font-flare text-[28px] font-normal text-dark-text leading-[1.05] tracking-[-0.02em] mb-3">
                Analyze
              </h3>
              <p className="font-sans text-[13px] leading-[1.7] text-light-text font-light mb-5">
                Data is rapidly parsed through an embedded RAG vector-database of accredited
                healthcare records.
              </p>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-black/[0.07]" />
                <span className="text-bright-green text-[15px] transition-transform duration-300 group-hover:translate-x-1.5 inline-block">
                  →
                </span>
              </div>
            </div>
          </div>

          {/* Card 4 — Receive */}
          <div
            className="process-card relative flex flex-col group cursor-pointer bg-white rounded-2xl overflow-hidden border border-black/[0.07] shadow-[0_2px_16px_-6px_rgba(0,0,0,0.08)]"
            style={cardTransition}
          >
            <span
              aria-hidden="true"
              className="absolute bottom-[-6px] right-3 z-0 select-none pointer-events-none font-flare text-[108px] leading-none text-black/[0.04] transition-colors duration-500 group-hover:text-[#44c767]/[0.08]"
            >
              04
            </span>
            <div className="overflow-hidden aspect-[3/4] relative">
              <Image
                src="/intelligence_health.png"
                alt="Receive guidance"
                fill
                className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    'linear-gradient(to top, #ffffff 0%, rgba(255,255,255,0.08) 42%, transparent 60%)',
                }}
              />
            </div>
            <div className="relative z-10 px-6 pt-2 pb-7 flex flex-col">
              <span className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-3">
                Guidance
              </span>
              <h3 className="font-flare text-[28px] font-normal text-dark-text leading-[1.05] tracking-[-0.02em] mb-3">
                Receive
              </h3>
              <p className="font-sans text-[13px] leading-[1.7] text-light-text font-light mb-5">
                Obtain actionable, non-diagnostic guidance advising self-care or timely medical
                consultation.
              </p>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-black/[0.07]" />
                <span className="text-bright-green text-[15px] transition-transform duration-300 group-hover:translate-x-1.5 inline-block">
                  →
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FINAL CTA BANNER ── */}
      <section className="bg-dark-green py-[80px] md:py-[120px] px-6 md:px-12 flex flex-col items-center justify-center text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(26,92,74,0.6)_0%,_transparent_70%)] pointer-events-none" />
        <div
          ref={ctaRef}
          className={`reveal max-w-[700px] relative z-10 w-full ${ctaVisible ? 'in-view' : ''}`}
        >
          <h2 className="font-flare text-[clamp(32px,6vw,70px)] font-normal text-cream leading-[1.1] mb-6">
            Gain clarity on your health.
          </h2>
          <p className="font-sans text-[15px] md:text-[16px] text-cream/70 font-light leading-[1.6] mb-10 max-w-[500px] mx-auto">
            Try the preliminary assessment engine and improve early health awareness with safe,
            guided AI support.
          </p>
          <div className="flex gap-4 justify-center flex-col sm:flex-row w-full sm:w-auto px-4 sm:px-0">
            <button
              onClick={handleStartAssessment}
              className="w-full sm:w-auto inline-block bg-bright-green text-white font-sans text-[15px] font-medium py-4 px-10 rounded-full tracking-[0.02em] transition-all duration-300 hover:bg-[#3ab55a] hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(68,199,103,0.3)] shadow-sm border border-transparent cursor-pointer"
            >
              Start Assessment
            </button>
            <a
              href="#how-it-works"
              className="w-full sm:w-auto inline-block text-cream font-sans text-[15px] font-normal py-[14px] px-8 rounded-full tracking-[0.02em] transition-all duration-300 border border-cream/30 hover:border-cream/80 hover:bg-white/5 hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(0,0,0,0.2)] bg-transparent cursor-pointer backdrop-blur-sm text-center"
            >
              Read the Science
            </a>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
