'use client';

import Image from 'next/image';
import Link from 'next/link';
import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';

export default function About() {
  return (
    <>
      <Header />

      {/* HERO — Split layout, team photo right */}
      <section className="relative w-full min-h-screen bg-[#162a1c] flex flex-col lg:flex-row overflow-hidden">
        {/* Left — text panel */}
        <div className="flex-1 flex flex-col justify-end px-6 md:px-14 lg:px-16 pt-36 pb-12 lg:pb-20 relative z-10">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-8 block">
            Team — Cybersprinter
          </span>
          <h1 className="font-flare text-[clamp(52px,8vw,120px)] font-normal leading-[0.88] text-cream tracking-[-0.03em] uppercase mb-10">
            We Build
            <br />
            <span className="italic">Health</span>
            <br />
            Intelligence.
          </h1>
          <p className="font-sans text-[14px] text-cream/55 font-light leading-[1.75] max-w-[360px]">
            A team of engineers, clinicians, and designers who believe that asking the right
            question at the right moment can change the course of someone&apos;s health.
          </p>
        </div>

        {/* Right — square photo panel */}
        <div className="w-full lg:w-[48%] flex-shrink-0 flex items-end justify-center lg:justify-end px-6 lg:px-0 pb-0 lg:pb-0 pt-8 lg:pt-28">
          <div className="relative w-full max-w-[480px] lg:max-w-none lg:w-full aspect-square lg:aspect-auto lg:h-full overflow-hidden">
            {/* decorative top-left accent */}
            <div className="absolute top-6 left-6 w-16 h-16 border-l-2 border-t-2 border-[#2ebd55]/60 z-10 pointer-events-none" />
            <div className="absolute bottom-6 right-6 w-16 h-16 border-r-2 border-b-2 border-[#2ebd55]/60 z-10 pointer-events-none" />
            <Image
              src="/yash.jpeg"
              alt="Cybersprinter Team"
              fill
              className="object-cover object-center"
              priority
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#162a1c]/60 via-transparent to-transparent lg:hidden" />
          </div>
        </div>
      </section>

      {/* MANIFESTO — Cream, large statement */}
      <section className="bg-[#f0ede6] py-20 md:py-32 px-6 md:px-14 lg:px-24 relative">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex flex-col md:flex-row gap-12 md:gap-20 items-start">
            <div className="shrink-0">
              <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text block mb-3">
                Our Belief
              </span>
              <div className="w-8 h-px bg-[#2ebd55]" />
            </div>
            <blockquote className="font-serif text-[clamp(22px,3.5vw,40px)] font-normal leading-[1.4] text-dark-text">
              &quot;The gap between feeling unwell and seeking help is where people are most
              vulnerable. We built Etheria to close that gap — with intelligence, not alarm.&quot;
              <footer className="mt-8 font-sans text-[12px] text-muted-text tracking-[0.1em] uppercase not-italic">
                — Cybersprinter, 2026
              </footer>
            </blockquote>
          </div>
        </div>
      </section>

      {/* PRINCIPLES — Numbered rows, editorial */}
      <section className="bg-[#f0ede6] pb-20 md:pb-32 px-6 md:px-14 lg:px-24 relative">
        <div className="max-w-[1100px] mx-auto border-t border-black/10 pt-12">
          <p className="font-sans text-[10px] tracking-[0.22em] uppercase text-muted-text mb-12">
            What We Stand For
          </p>
          <div className="flex flex-col divide-y divide-black/8">
            <div className="flex flex-col sm:flex-row sm:items-start gap-4 sm:gap-12 py-10 group">
              <span className="font-sans text-[11px] text-muted-text/50 tracking-widest shrink-0 pt-1">
                01
              </span>
              <div className="flex-1 flex flex-col sm:flex-row gap-4 sm:gap-16">
                <h3 className="font-flare text-[clamp(28px,3.5vw,44px)] font-normal text-dark-text leading-none tracking-[-0.02em] shrink-0 w-full sm:w-[240px]">
                  Innovation
                </h3>
                <p className="font-sans text-[14px] text-muted-text leading-[1.75] font-light max-w-[500px] pt-1">
                  An AI health assistant built around India: Indian brand names, India-common
                  conditions, and emergency routing to 112, 108 and Tele-MANAS 14416.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-start gap-4 sm:gap-12 py-10 group">
              <span className="font-sans text-[11px] text-muted-text/50 tracking-widest shrink-0 pt-1">
                02
              </span>
              <div className="flex-1 flex flex-col sm:flex-row gap-4 sm:gap-16">
                <h3 className="font-flare text-[clamp(28px,3.5vw,44px)] font-normal text-dark-text leading-none tracking-[-0.02em] shrink-0 w-full sm:w-[240px]">
                  Safety First
                </h3>
                <p className="font-sans text-[14px] text-muted-text leading-[1.75] font-light max-w-[500px] pt-1">
                  Safety rules are code, not prompts: red-flag triage runs before the model speaks,
                  every reply is filtered for diagnoses and doses, and no drug pair is ever called
                  safe.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-start gap-4 sm:gap-12 py-10 group">
              <span className="font-sans text-[11px] text-muted-text/50 tracking-widest shrink-0 pt-1">
                03
              </span>
              <div className="flex-1 flex flex-col sm:flex-row gap-4 sm:gap-16">
                <h3 className="font-flare text-[clamp(28px,3.5vw,44px)] font-normal text-dark-text leading-none tracking-[-0.02em] shrink-0 w-full sm:w-[240px]">
                  Accessibility
                </h3>
                <p className="font-sans text-[14px] text-muted-text leading-[1.75] font-light max-w-[500px] pt-1">
                  No forms, no jargon: describe what you feel in your own words, and get plain
                  answers with the sources they came from.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* OUR TEAM — Dark, photo centered in square with stats */}
      <section className="bg-[#0f1b13] py-20 md:py-32 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex flex-col lg:flex-row gap-16 lg:gap-24 items-start">
            {/* Photo — square, constrained */}
            <div className="w-full lg:w-[420px] shrink-0">
              <div className="relative w-full aspect-square overflow-hidden rounded-2xl ring-1 ring-white/10">
                <Image
                  src="/aboutus.jpeg"
                  alt="Cybersprinter Team"
                  fill
                  className="object-cover object-center"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0f1b13]/50 to-transparent" />
              </div>
              <p className="font-sans text-[11px] text-cream/30 tracking-[0.12em] uppercase mt-4">
                Cybersprinter · 2025
              </p>
            </div>

            {/* Right — content */}
            <div className="flex-1 flex flex-col justify-center pt-0 lg:pt-8">
              <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/30 mb-6 block">
                Our Team
              </span>
              <h2 className="font-serif text-[clamp(28px,4vw,48px)] font-light text-cream leading-[1.25] mb-8">
                People who care deeply about getting this right.
              </h2>
              <p className="font-sans text-[14px] text-cream/55 leading-[1.8] font-light mb-10 max-w-[460px]">
                We&apos;re not just building a product. We&apos;re challenging how people interact
                with their health. That takes engineers who obsess over details, clinicians who
                won&apos;t let us cut corners, and designers who refuse to make health feel
                intimidating.
              </p>

              {/* Divider stats */}
              <div className="grid grid-cols-2 gap-y-8 border-t border-white/10 pt-10 max-w-[400px]">
                <div>
                  <p className="font-flare text-[36px] font-normal text-[#44c767] leading-none mb-1">
                    4
                  </p>
                  <p className="font-sans text-[11px] text-cream/40 tracking-wide">Team members</p>
                </div>
                <div>
                  <p className="font-flare text-[36px] font-normal text-[#44c767] leading-none mb-1">
                    2023
                  </p>
                  <p className="font-sans text-[11px] text-cream/40 tracking-wide">Founded</p>
                </div>
                <div>
                  <p className="font-flare text-[36px] font-normal text-[#44c767] leading-none mb-1">
                    Agentic AI
                  </p>
                  <p className="font-sans text-[11px] text-cream/40 tracking-wide">
                    Core technology
                  </p>
                </div>
                <div>
                  <p className="font-flare text-[36px] font-normal text-[#44c767] leading-none mb-1">
                    100%
                  </p>
                  <p className="font-sans text-[11px] text-cream/40 tracking-wide">Safety-first</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA — minimal, dark-to-warm */}
      <section className="bg-[#0f1b13] pb-24 md:pb-32 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto border-t border-white/10 pt-16 flex flex-col md:flex-row md:items-end justify-between gap-10">
          <div>
            <p className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/30 mb-5">
              Work With Us
            </p>
            <h3 className="font-serif text-[clamp(24px,4vw,48px)] font-light text-cream leading-[1.2] max-w-[480px]">
              Passionate about health tech?
              <br />
              We&apos;d love to hear from you.
            </h3>
          </div>
          <div className="flex gap-3 shrink-0">
            <a
              href="https://group-portfolio-five.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-[#2ebd55] text-white font-sans text-[14px] font-medium py-3 px-8 rounded-full tracking-[0.02em] transition-all duration-300 hover:bg-[#3ab55a] hover:-translate-y-0.5 hover:shadow-[0_8px_20px_rgba(68,199,103,0.25)] cursor-pointer"
            >
              Portfolio
            </a>
            <Link
              href="/contact"
              className="inline-block text-cream font-sans text-[14px] font-normal py-3 px-7 rounded-full tracking-[0.02em] transition-all duration-300 border border-cream/20 hover:border-cream/60 hover:bg-white/5 bg-transparent cursor-pointer"
            >
              Contact Us
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
