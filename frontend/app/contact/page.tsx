'use client';

import { useState } from 'react';
import Header from '@/src/components/Header';
import Footer from '@/src/components/Footer';

export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // Simulate send — wire to a real email/form endpoint when ready
    await new Promise((r) => setTimeout(r, 900));
    setSent(true);
    setLoading(false);
  };

  return (
    <>
      <Header />

      {/* HERO */}
      <section className="relative w-full min-h-[55vh] bg-[#162a1c] flex flex-col justify-end px-6 md:px-14 lg:px-24 pt-36 pb-14 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[70vw] h-[70vw] max-w-[700px] rounded-full bg-[radial-gradient(circle,_rgba(68,199,103,0.18)_0%,_transparent_65%)] blur-[90px]" />
        </div>
        <div className="relative z-10 max-w-[900px]">
          <span className="font-sans text-[10px] tracking-[0.22em] uppercase text-cream/40 mb-6 block">
            Get In Touch
          </span>
          <h1 className="font-flare text-[clamp(48px,8vw,110px)] font-normal leading-[0.9] text-cream tracking-[-0.03em] uppercase">
            Let&apos;s
            <br />
            <span className="italic">Talk.</span>
          </h1>
          <p className="mt-8 font-sans text-[15px] text-cream/55 font-light leading-[1.75] max-w-[440px]">
            Questions about Etheria, research collaborations, or partnership opportunities — we read
            every message.
          </p>
        </div>
      </section>

      {/* FORM + SIDEBAR */}
      <section className="bg-[#f0ede6] py-20 md:py-28 px-6 md:px-14 lg:px-24">
        <div className="max-w-[1100px] mx-auto grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-16">
          {/* Form */}
          <div>
            {sent ? (
              <div className="flex flex-col items-start gap-5 py-10">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#2ebd55]/15">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#2ebd55"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <h2 className="font-serif text-[28px] text-dark-text font-light">Message sent</h2>
                <p className="font-sans text-[14px] text-muted-text leading-[1.7] max-w-[400px]">
                  Thanks for reaching out. We aim to respond within 1–2 business days.
                </p>
                <button
                  onClick={() => {
                    setSent(false);
                    setName('');
                    setEmail('');
                    setSubject('');
                    setMessage('');
                  }}
                  className="mt-2 font-sans text-[13px] text-[#2ebd55] hover:underline"
                >
                  Send another message
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div className="flex flex-col gap-2">
                    <label className="font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-text">
                      Full name
                    </label>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Jane Smith"
                      className="h-[50px] rounded-xl border border-black/[0.08] bg-white px-4 font-sans text-[14px] text-dark-text outline-none transition-all focus:border-[#2ebd55] focus:shadow-[0_0_0_3px_rgba(46,189,85,0.1)]"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-text">
                      Email address
                    </label>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="jane@example.com"
                      className="h-[50px] rounded-xl border border-black/[0.08] bg-white px-4 font-sans text-[14px] text-dark-text outline-none transition-all focus:border-[#2ebd55] focus:shadow-[0_0_0_3px_rgba(46,189,85,0.1)]"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-text">
                    Subject
                  </label>
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    required
                    className="h-[50px] rounded-xl border border-black/[0.08] bg-white px-4 font-sans text-[14px] text-dark-text outline-none transition-all focus:border-[#2ebd55] appearance-none"
                  >
                    <option value="">Select a topic…</option>
                    <option value="general">General inquiry</option>
                    <option value="research">Research collaboration</option>
                    <option value="partnership">Partnership / enterprise</option>
                    <option value="press">Press & media</option>
                    <option value="support">Technical support</option>
                    <option value="feedback">Product feedback</option>
                  </select>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-text">
                    Message
                  </label>
                  <textarea
                    required
                    rows={6}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Tell us about your project, question, or idea…"
                    className="rounded-xl border border-black/[0.08] bg-white px-4 py-3 font-sans text-[14px] text-dark-text outline-none transition-all resize-none focus:border-[#2ebd55] focus:shadow-[0_0_0_3px_rgba(46,189,85,0.1)]"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="self-start bg-[#162a1c] text-[#44c767] font-sans text-[14px] font-medium py-3.5 px-10 rounded-full tracking-[0.02em] transition-all hover:bg-[#1f3826] hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(22,42,28,0.2)] disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {loading ? 'Sending…' : 'Send message'}
                </button>
              </form>
            )}
          </div>

          {/* Sidebar */}
          <div className="flex flex-col gap-10 pt-2">
            <div>
              <span className="font-sans text-[10px] tracking-[0.2em] uppercase text-muted-text block mb-4">
                Email
              </span>
              <a
                href="mailto:hello@etheria.health"
                className="font-serif text-[18px] text-dark-text hover:text-[#2ebd55] transition-colors"
              >
                hello@etheria.health
              </a>
            </div>
            <div>
              <span className="font-sans text-[10px] tracking-[0.2em] uppercase text-muted-text block mb-4">
                Response time
              </span>
              <p className="font-sans text-[14px] text-dark-text/70 leading-[1.65]">
                We respond to all inquiries within 1–2 business days, Monday–Friday.
              </p>
            </div>
            <div>
              <span className="font-sans text-[10px] tracking-[0.2em] uppercase text-muted-text block mb-4">
                For researchers
              </span>
              <p className="font-sans text-[14px] text-dark-text/70 leading-[1.65]">
                Academic and clinical research partnerships are welcome. Please select
                &ldquo;Research collaboration&rdquo; in the subject field and attach any relevant
                context.
              </p>
            </div>
            <div className="pt-4 border-t border-black/[0.06]">
              <span className="font-sans text-[10px] tracking-[0.2em] uppercase text-muted-text block mb-4">
                Follow us
              </span>
              <div className="flex gap-3">
                {['LinkedIn', 'X / Twitter', 'Instagram'].map((s) => (
                  <span
                    key={s}
                    className="font-sans text-[12px] text-dark-text/40 border border-black/10 rounded-full px-3 py-1"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
