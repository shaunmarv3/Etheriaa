'use client';

import { signUp, useAuth } from '../../../src/lib/auth';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

const MIN_PASSWORD = 10; // spec 9

export default function SignUpPage() {
  const auth = useAuth();
  const router = useRouter();

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (auth.isLoaded && auth.isSignedIn) router.push('/dashboard');
  }, [auth.isLoaded, auth.isSignedIn, router]);

  const handleEmailSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setLocalError('');
    try {
      const displayName = [firstName, lastName]
        .map((x) => x.trim())
        .filter(Boolean)
        .join(' ');
      await signUp(email, password, displayName || undefined);
      router.push('/dashboard');
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const displayError = localError;
  const isLoading = loading;

  return (
    <div className="min-h-screen flex overflow-hidden">
      {/* ── LEFT PANEL — brand / editorial ── */}
      <div className="hidden lg:flex lg:w-[58%] xl:w-[62%] relative flex-col justify-between bg-[#162a1c] overflow-hidden px-12 xl:px-16 py-10">
        {/* Mesh gradient orbs */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-8%] left-1/2 -translate-x-1/2 w-[85vw] h-[85vw] max-w-[900px] max-h-[900px] rounded-full bg-[radial-gradient(circle,_rgba(255,255,255,0.85)_0%,_rgba(68,199,103,0.75)_22%,_transparent_58%)] blur-[110px] mix-blend-screen opacity-80" />
          <div className="absolute bottom-[-20%] right-[-15%] w-[60vw] h-[60vw] max-w-[700px] max-h-[700px] rounded-full bg-[radial-gradient(circle,_rgba(68,199,103,0.45)_0%,_transparent_68%)] blur-[80px] mix-blend-screen" />
          <div className="absolute top-[40%] left-[-18%] w-[50vw] h-[50vw] max-w-[550px] max-h-[550px] rounded-full bg-[radial-gradient(circle,_rgba(46,125,107,0.55)_0%,_transparent_68%)] blur-[70px] mix-blend-screen" />
        </div>

        {/* Logo */}
        <div className="relative z-10">
          <Link href="/">
            <Image
              src="/logo-light.png"
              alt="Etheria"
              width={120}
              height={36}
              style={{ height: '34px', width: 'auto' }}
              priority
            />
          </Link>
        </div>

        {/* Display type */}
        <div className="relative z-10 w-full">
          <p className="font-sans text-[11px] font-medium tracking-[0.22em] uppercase text-bright-green mb-6 opacity-90">
            Health Assessment Platform
          </p>

          <h1 className="font-flare text-[clamp(56px,8vw,130px)] font-normal leading-[0.88] text-cream tracking-[-0.03em] uppercase">
            <span className="block text-left">YOUR</span>
            <span className="block italic text-right pr-0 xl:pr-4 mt-1">HEALTH</span>
          </h1>

          <div className="mt-10 h-px w-[60%] bg-gradient-to-r from-cream/15 to-transparent" />

          <p className="mt-6 font-sans text-[14px] leading-[1.7] text-cream/55 font-light max-w-[360px]">
            Create your account and start understanding your health with calm, AI-guided assessment
            grounded in your own reports.
          </p>
        </div>

        {/* Bottom trust line */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-1.5 h-1.5 rounded-full bg-bright-green animate-pulse" />
          <span className="font-sans text-[11px] tracking-[0.14em] uppercase text-cream/40">
            RAG-powered · Medically grounded
          </span>
        </div>
      </div>

      {/* ── RIGHT PANEL — form ── */}
      <div className="w-full lg:w-[42%] xl:w-[38%] flex flex-col justify-between bg-[#f5f2ec] relative overflow-hidden">
        {/* Top accent bar for mobile */}
        <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-bright-green/60 via-bright-green/20 to-transparent lg:hidden" />

        {/* Mobile logo */}
        <div className="lg:hidden px-6 pt-8 pb-0">
          <Link href="/">
            <Image
              src="/logo-light.png"
              alt="Etheria"
              width={100}
              height={30}
              style={{
                height: '28px',
                width: 'auto',
                filter: 'invert(1) sepia(1) saturate(0) brightness(0.2)',
              }}
              priority
            />
          </Link>
        </div>

        {/* Scrollable form area */}
        <div className="flex-1 flex flex-col justify-center px-8 sm:px-12 lg:px-10 xl:px-14 py-10 overflow-y-auto">
          <>
            <div className="mb-8">
              <p className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-3">
                Create Account
              </p>
              <h2 className="font-flare text-[clamp(28px,4vw,42px)] font-normal text-dark-text leading-[0.95] tracking-[-0.025em]">
                Start your
                <br />
                <span className="italic">assessment.</span>
              </h2>
            </div>

            {displayError && (
              <div className="mb-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3.5">
                <svg
                  className="mt-0.5 h-4 w-4 shrink-0 text-red-500"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <p className="font-sans text-[13px] leading-[1.5] text-red-700">{displayError}</p>
              </div>
            )}

            <div className="space-y-7">
              <form onSubmit={handleEmailSignUp} className="space-y-4">
                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="group space-y-2">
                    <label
                      htmlFor="first-name"
                      className="block font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-light-text transition-colors duration-200 group-focus-within:text-stat-green"
                    >
                      First Name
                    </label>
                    <input
                      id="first-name"
                      type="text"
                      disabled={isLoading}
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="Jane"
                      className="h-[52px] w-full rounded-2xl border border-black/[0.07] bg-white/80 px-4 font-sans text-[15px] text-dark-text outline-none transition-all duration-200 placeholder:text-muted-text/40 focus:border-bright-green focus:bg-white focus:shadow-[0_0_0_4px_rgba(68,199,103,0.12)] disabled:cursor-not-allowed disabled:opacity-60"
                    />
                  </div>
                  <div className="group space-y-2">
                    <label
                      htmlFor="last-name"
                      className="block font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-light-text transition-colors duration-200 group-focus-within:text-stat-green"
                    >
                      Last Name
                    </label>
                    <input
                      id="last-name"
                      type="text"
                      disabled={isLoading}
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Doe"
                      className="h-[52px] w-full rounded-2xl border border-black/[0.07] bg-white/80 px-4 font-sans text-[15px] text-dark-text outline-none transition-all duration-200 placeholder:text-muted-text/40 focus:border-bright-green focus:bg-white focus:shadow-[0_0_0_4px_rgba(68,199,103,0.12)] disabled:cursor-not-allowed disabled:opacity-60"
                    />
                  </div>
                </div>

                {/* Email */}
                <div className="group space-y-2">
                  <label
                    htmlFor="email"
                    className="block font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-light-text transition-colors duration-200 group-focus-within:text-stat-green"
                  >
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    disabled={isLoading}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@etheria.ai"
                    className="h-[52px] w-full rounded-2xl border border-black/[0.07] bg-white/80 px-4 font-sans text-[15px] text-dark-text outline-none transition-all duration-200 placeholder:text-muted-text/40 focus:border-bright-green focus:bg-white focus:shadow-[0_0_0_4px_rgba(68,199,103,0.12)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </div>

                {/* Password */}
                <div className="group space-y-2">
                  <label
                    htmlFor="password"
                    className="block font-sans text-[10px] font-semibold uppercase tracking-[0.2em] text-light-text transition-colors duration-200 group-focus-within:text-stat-green"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      minLength={MIN_PASSWORD}
                      disabled={isLoading}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min. 10 characters"
                      className="h-[52px] w-full rounded-2xl border border-black/[0.07] bg-white/80 px-4 pr-12 font-sans text-[15px] text-dark-text outline-none transition-all duration-200 placeholder:text-muted-text/40 focus:border-bright-green focus:bg-white focus:shadow-[0_0_0_4px_rgba(68,199,103,0.12)] disabled:cursor-not-allowed disabled:opacity-60"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-light-text/60 hover:text-light-text transition-colors"
                      tabIndex={-1}
                    >
                      {showPassword ? (
                        <svg
                          width="17"
                          height="17"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                          <line x1="1" y1="1" x2="23" y2="23" />
                        </svg>
                      ) : (
                        <svg
                          width="17"
                          height="17"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                  </div>
                  {/* Password strength hint */}
                  {password.length > 0 && (
                    <div className="flex items-center gap-2 pt-1">
                      {[...Array(4)].map((_, i) => {
                        const strength = Math.min(Math.floor(password.length / 3), 4);
                        return (
                          <div
                            key={i}
                            className={`h-0.5 flex-1 rounded-full transition-all duration-300 ${
                              i < strength
                                ? strength <= 1
                                  ? 'bg-red-400'
                                  : strength <= 2
                                    ? 'bg-amber-400'
                                    : strength <= 3
                                      ? 'bg-yellow-400'
                                      : 'bg-bright-green'
                                : 'bg-black/[0.07]'
                            }`}
                          />
                        );
                      })}
                      <span className="font-sans text-[10px] text-light-text/60 shrink-0">
                        {password.length < 4
                          ? 'Weak'
                          : password.length < 7
                            ? 'Fair'
                            : password.length < 10
                              ? 'Good'
                              : 'Strong'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex h-[52px] w-full items-center justify-center rounded-full bg-[#162a1c] font-sans text-[14px] font-medium tracking-[0.04em] text-cream transition-all duration-300 hover:-translate-y-1 hover:bg-[#1d3a26] hover:shadow-[0_14px_32px_-8px_rgba(22,42,28,0.35)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:translate-y-0 disabled:hover:shadow-none mt-1"
                >
                  {isLoading ? (
                    <span className="h-4 w-4 rounded-full border-2 border-cream/30 border-t-cream animate-spin" />
                  ) : (
                    <span className="flex items-center gap-2.5">
                      Create Account
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </span>
                  )}
                </button>
              </form>
            </div>
          </>
        </div>

        {/* Footer */}
        <div className="px-8 sm:px-12 lg:px-10 xl:px-14 pb-8 pt-4 border-t border-black/[0.06]">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <p className="font-sans text-[13px] text-muted-text leading-[1.5]">
              Already have an account?{' '}
              <Link
                href="/sign-in"
                className="font-medium text-bright-green underline decoration-bright-green/30 underline-offset-4 transition-colors hover:decoration-bright-green"
              >
                Sign in
              </Link>
            </p>
            <p className="font-sans text-[11px] text-light-text/60 leading-[1.5] flex items-center gap-1.5">
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="shrink-0"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Files encrypted at rest
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
