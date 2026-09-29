'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../lib/auth';

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const router = useRouter();
  const { isSignedIn } = useAuth();

  const handleAssessment = () => {
    setMenuOpen(false);
    router.push(isSignedIn ? '/dashboard' : '/sign-in');
  };

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      {/* Click outside overlay (Whitish blurred background) */}
      <div
        className={`fixed inset-0 z-[190] transition-all duration-300 ease-out ${
          menuOpen
            ? 'bg-white/20 backdrop-blur-md opacity-100 pointer-events-auto'
            : 'bg-transparent backdrop-blur-none opacity-0 pointer-events-none'
        }`}
        onClick={() => setMenuOpen(false)}
      />

      {/* NAV WRAPPER (Everything is anchored here now) */}
      <div
        className={`fixed top-[6px] left-1/2 -translate-x-1/2 z-[200] w-full max-w-[800px] px-3 transition-all duration-[300ms] ease-out flex flex-col items-center h-[calc(100vh-12px)] pointer-events-none`}
      >
        {/*
          THE MAIN CONTAINER (Navbar Pill)
        */}
        <div
          className={`w-full max-w-[640px] shrink-0 transition-all duration-300 ease-out pointer-events-auto rounded-lg ${
            menuOpen
              ? 'bg-[#1a2e20] shadow-md border border-white/20'
              : scrolled
                ? 'bg-[#d1ccc3]/70 backdrop-blur-[25px] shadow-sm'
                : 'bg-transparent backdrop-blur-none'
          }`}
        >
          {/* TOP BAR / HEADER (Always visible) */}
          <header
            className={`flex items-center justify-between h-14 pointer-events-auto transition-all duration-300 w-full ${
              menuOpen ? 'text-cream px-6' : scrolled ? 'text-dark-text px-2' : 'text-cream px-2'
            }`}
          >
            {/* LEFT — System / Knowledge */}
            <div
              className={`flex-1 transition-opacity duration-300 hidden md:flex ${menuOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
            >
              <nav>
                <ul className="flex items-center gap-2 m-0 p-0 list-none">
                  <li>
                    <Link
                      href="/sign-in"
                      className="flex items-center justify-center h-10 px-4 rounded text-inherit transition-colors duration-100 ease-out hover:bg-black/10 font-serif text-base font-[350] tracking-normal"
                    >
                      <span>System</span>
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/knowledge-base"
                      className="flex items-center justify-center h-10 px-4 rounded text-inherit transition-colors duration-100 ease-out hover:bg-black/10 font-serif text-base font-[350] tracking-normal"
                    >
                      <span>Knowledge</span>
                    </Link>
                  </li>
                </ul>
              </nav>
            </div>

            {/* CENTER — Logo image */}
            <div className="flex-1 flex justify-start md:justify-center">
              <Link
                href="/"
                className="flex items-center justify-center text-inherit decoration-none hover:opacity-80 transition-opacity"
                onClick={() => setMenuOpen(false)}
              >
                <span className="font-flare text-2xl md:text-3xl font-normal tracking-wide text-inherit">
                  Etheria
                </span>
              </Link>
            </div>

            {/* RIGHT — Hamburger / Close */}
            <div className="flex-1 flex justify-end">
              {!menuOpen ? (
                <button
                  className={`flex items-center justify-center h-10 w-10 rounded border bg-transparent cursor-pointer p-2 transition-colors duration-150 ease-out hover:bg-black/5 ${
                    scrolled ? 'border-black/20 text-dark-text' : 'border-white/35 text-cream'
                  }`}
                  onClick={() => setMenuOpen(true)}
                  aria-label="Open menu"
                >
                  <svg
                    width="9"
                    height="14"
                    viewBox="0 0 9 14"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="fill-current w-full h-full"
                  >
                    <path d="M7.75 12C8.16421 12 8.5 12.3358 8.5 12.75C8.5 13.1642 8.16421 13.5 7.75 13.5H0.75C0.335786 13.5 0 13.1642 0 12.75C0 12.3358 0.335786 12 0.75 12H7.75ZM7.75 6C8.16421 6 8.5 6.33579 8.5 6.75C8.5 7.16421 8.16421 7.5 7.75 7.5H0.75C0.335786 7.5 0 7.16421 0 6.75C0 6.33579 0.335786 6 0.75 6H7.75ZM7.75 0C8.16421 1.28852e-07 8.5 0.335787 8.5 0.75C8.5 1.16421 8.16421 1.5 7.75 1.5H0.75C0.335786 1.5 0 1.16421 0 0.75C0 0.335786 0.335786 0 0.75 0H7.75Z" />
                  </svg>
                </button>
              ) : (
                <button
                  className="flex items-center justify-center h-10 w-10 rounded border border-white/40 bg-transparent cursor-pointer text-white/70 transition-colors duration-150 ease-out hover:bg-white/10 hover:text-white"
                  onClick={() => setMenuOpen(false)}
                  aria-label="Close menu"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M1 1L13 13M1 13L13 1" />
                  </svg>
                </button>
              )}
            </div>
          </header>
        </div>

        {/* 
          DROPDOWN PAYLOAD 
          Distinct box with a gap (mt-2 or similar). 
          Uses translate and opacity for a smoother entering/exiting aesthetic
        */}
        <div
          className={`w-full max-w-[640px] mt-2 overflow-hidden transition-[height,opacity] duration-300 flex flex-col rounded-lg ${
            menuOpen
              ? 'opacity-100 pointer-events-auto shadow-2xl bg-[#1a2e20]'
              : 'opacity-0 pointer-events-none bg-transparent absolute'
          }`}
          style={{
            height: menuOpen ? 'calc(100vh - 80px)' : '0',
            transitionTimingFunction: menuOpen ? 'ease-out' : 'ease-in',
          }}
        >
          {/* Main Links Area (Dark Green) */}
          <div
            className={`flex-1 flex flex-col justify-center items-center py-10 px-6 overflow-hidden transition-opacity duration-200 ${menuOpen ? 'opacity-100' : 'opacity-0'}`}
          >
            <nav className="flex flex-col items-center gap-0 mb-12">
              <button
                className="font-serif text-[clamp(28px,5vw,50px)] text-cream font-light tracking-[-0.02em] leading-[1.15] hover:opacity-75 transition-opacity bg-transparent border-none cursor-pointer"
                onClick={handleAssessment}
              >
                Assessment
              </button>
              <Link
                href="/knowledge-base"
                className="font-serif text-[clamp(28px,5vw,50px)] text-cream font-light tracking-[-0.02em] leading-[1.15] hover:opacity-75 transition-opacity"
                onClick={() => setMenuOpen(false)}
              >
                Knowledge Base
              </Link>
              <Link
                href="/security"
                className="font-serif text-[clamp(28px,5vw,50px)] text-cream font-light tracking-[-0.02em] leading-[1.15] hover:opacity-75 transition-opacity"
                onClick={() => setMenuOpen(false)}
              >
                Security
              </Link>
              <Link
                href="/about"
                className="font-serif text-[clamp(28px,5vw,50px)] text-cream font-light tracking-[-0.02em] leading-[1.15] hover:opacity-75 transition-opacity"
                onClick={() => setMenuOpen(false)}
              >
                About
              </Link>
              <Link
                href="/contact"
                className="font-serif text-[clamp(28px,5vw,50px)] text-cream font-light tracking-[-0.02em] leading-[1.15] hover:opacity-75 transition-opacity"
                onClick={() => setMenuOpen(false)}
              >
                Contact
              </Link>
            </nav>

            <div className="flex flex-col items-center gap-2">
              <span className="font-sans text-[10px] tracking-[0.1em] text-cream/50 uppercase mb-1">
                RESOURCES
              </span>
              <Link
                href="/knowledge-base"
                className="font-sans text-[13px] text-cream hover:opacity-75 transition-opacity font-light"
                onClick={() => setMenuOpen(false)}
              >
                Medical Guidelines
              </Link>
              <button
                className="font-sans text-[13px] text-cream hover:opacity-75 transition-opacity font-light bg-transparent border-none cursor-pointer"
                onClick={handleAssessment}
              >
                Interactive Demos
              </button>
              <Link
                href="/research"
                className="font-sans text-[13px] text-cream hover:opacity-75 transition-opacity font-light"
                onClick={() => setMenuOpen(false)}
              >
                Research Papers
              </Link>
            </div>
          </div>

          {/* Bottom Bar (White/Cream) */}
          <div
            className={`bg-[#f0ede6] px-6 md:px-12 py-4 flex flex-wrap justify-between items-center gap-4 shrink-0 transition-opacity duration-200 ${menuOpen ? 'opacity-100' : 'opacity-0'}`}
          >
            <a
              href="https://group-portfolio-five.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-sans text-xs text-dark-text hover:opacity-70 transition-opacity whitespace-nowrap"
            >
              Join The Team
            </a>
            <div className="flex flex-wrap justify-center gap-x-3 gap-y-2">
              {[
                { label: 'LinkedIn', href: 'https://linkedin.com' },
                { label: 'Instagram', href: 'https://instagram.com' },
                { label: 'YouTube', href: 'https://youtube.com' },
                { label: 'Spotify', href: 'https://spotify.com' },
                { label: 'Apple Podcasts', href: 'https://podcasts.apple.com' },
                { label: 'TikTok', href: 'https://tiktok.com' },
              ].map(({ label, href }) => (
                <a
                  key={label}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-sans text-xs text-dark-text hover:opacity-70 transition-opacity"
                >
                  {label}
                </a>
              ))}
            </div>
            <div className="flex gap-2 whitespace-nowrap">
              <Link
                href="/terms"
                onClick={() => setMenuOpen(false)}
                className="font-sans text-[9px] text-dark-text/70 border border-dark-text/20 rounded px-1.5 py-1 bg-white hover:bg-black/5 transition-colors"
              >
                Terms of use
              </Link>
              <Link
                href="/privacy"
                onClick={() => setMenuOpen(false)}
                className="font-sans text-[9px] text-dark-text/70 border border-dark-text/20 rounded px-1.5 py-1 bg-white hover:bg-black/5 transition-colors"
              >
                Cookie & privacy policy
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
