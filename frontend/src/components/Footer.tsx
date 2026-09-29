import Link from 'next/link';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="relative bg-[#0c130f] border-t border-white/5 overflow-hidden text-cream pt-20 sm:pt-32">
      {/* Background ambient glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-[#44c767] opacity-[0.03] blur-[150px] pointer-events-none rounded-full" />

      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 relative z-10">
        <div className="flex flex-col lg:flex-row justify-between items-start gap-16 lg:gap-24 mb-24">
          {/* Main Brand Section */}
          <div className="max-w-md">
            <h2 className="font-serif text-5xl md:text-7xl font-light tracking-tight text-white mb-6 hover:text-[#44c767] transition-colors duration-500">
              Etheria.
            </h2>
            <p className="font-sans text-sm md:text-base leading-relaxed text-cream/40 mb-10 w-[90%]">
              Pioneering interactive health assessment with state-of-the-art context-aware models.
              Secure, private, and deeply intelligent.
            </p>

            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center w-12 h-12 rounded-full border border-white/10 hover:border-[#44c767]/50 hover:bg-[#44c767]/10 transition-all cursor-pointer group">
                <svg
                  className="w-4 h-4 text-white/50 group-hover:text-[#44c767] transition-colors"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z" />
                </svg>
              </div>
              <div className="flex items-center justify-center w-12 h-12 rounded-full border border-white/10 hover:border-[#44c767]/50 hover:bg-[#44c767]/10 transition-all cursor-pointer group">
                <svg
                  className="w-5 h-5 text-white/50 group-hover:text-[#44c767] transition-colors"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.359 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.415-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678c-3.405 0-6.162 2.76-6.162 6.162 0 3.405 2.757 6.162 6.162 6.162 3.405 0 6.162-2.757 6.162-6.162 0-3.402-2.757-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
                </svg>
              </div>
              <div className="flex items-center justify-center w-12 h-12 rounded-full border border-white/10 hover:border-[#44c767]/50 hover:bg-[#44c767]/10 transition-all cursor-pointer group">
                <svg
                  className="w-5 h-5 text-white/50 group-hover:text-[#44c767] transition-colors"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
                </svg>
              </div>
            </div>
          </div>

          {/* Links Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-12 gap-y-16 w-full max-w-2xl">
            {/* Column 1 */}
            <div className="flex flex-col">
              <h4 className="font-sans text-xs font-semibold tracking-[0.2em] uppercase text-white mb-6 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#44c767]"></span>
                Platform
              </h4>
              <ul className="flex flex-col gap-4">
                <li>
                  <Link
                    href="/dashboard"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Assistant{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/knowledge-base"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    RAG Integration{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/security"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Data Security{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/contact"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Pricing Models{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 2 */}
            <div className="flex flex-col">
              <h4 className="font-sans text-xs font-semibold tracking-[0.2em] uppercase text-white mb-6 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#44c767]/50"></span>
                Resources
              </h4>
              <ul className="flex flex-col gap-4">
                <li>
                  <Link
                    href="/knowledge-base"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Documentation{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/security"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Medical Compliance{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/research"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    API Reference{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/contact"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Status Page{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 3 */}
            <div className="flex flex-col">
              <h4 className="font-sans text-xs font-semibold tracking-[0.2em] uppercase text-white mb-6 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full border border-[#44c767]"></span>
                Company
              </h4>
              <ul className="flex flex-col gap-4">
                <li>
                  <Link
                    href="/about"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Our Story{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <Link
                    href="/blog"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Insights &amp; News{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
                <li>
                  <a
                    href="https://group-portfolio-five.vercel.app/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Careers{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </a>
                </li>
                <li>
                  <Link
                    href="/contact"
                    className="font-sans text-[13px] text-cream/50 hover:text-white transition-colors block w-fit group"
                  >
                    Contact{' '}
                    <span className="block h-px w-0 bg-[#44c767] transition-all duration-300 group-hover:w-full"></span>
                  </Link>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Newsletter/CTA Box */}
        <div className="w-full bg-white/[0.02] border border-white/5 rounded-2xl p-6 md:p-10 mb-20 flex flex-col md:flex-row items-center justify-between gap-8 hover:bg-white/[0.04] transition-colors duration-500 group relative overflow-hidden">
          {/* Shine effect */}
          <div className="absolute inset-0 w-[200%] h-full bg-gradient-to-r from-transparent via-white/[0.05] to-transparent -translate-x-[150%] skew-x-[-45deg] group-hover:animate-[shine_3s_ease-out_infinite]" />

          <div className="max-w-xl relative z-10">
            <h3 className="font-serif text-2xl text-white mb-2 font-light">
              Stay at the forefront of medical AI.
            </h3>
            <p className="font-sans text-sm text-cream/40">
              Subscribe for early access features, research papers, and platform updates.
            </p>
          </div>
          <div className="w-full md:w-auto flex flex-col sm:flex-row gap-3 relative z-10">
            <input
              type="email"
              placeholder="Enter your email"
              className="bg-[#0c130f] border border-white/10 rounded-xl px-5 py-3.5 text-sm outline-none focus:border-[#44c767]/50 focus:ring-1 focus:ring-[#44c767]/30 transition-all text-white min-w-[280px]"
            />
            <button className="bg-white text-[#0c130f] hover:bg-[#44c767] hover:text-white font-sans text-xs uppercase tracking-widest font-semibold py-3.5 px-6 rounded-xl transition-all duration-300 whitespace-nowrap">
              Subscribe
            </button>
          </div>
        </div>

        {/* Bottom Lockup */}
        <div className="border-t border-white/5 py-8 flex flex-col mt-4">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6 w-full text-center md:text-left">
            <p className="font-sans text-[11px] text-cream/30 uppercase tracking-widest order-2 md:order-1">
              &copy; {currentYear} Etheria Technologies Inc. All rights reserved.
            </p>
            <div className="flex flex-wrap justify-center items-center gap-6 md:gap-8 order-1 md:order-2">
              <Link
                href="/privacy"
                className="font-sans text-[11px] text-cream/30 hover:text-white uppercase tracking-widest transition-colors"
              >
                Privacy Policy
              </Link>
              <Link
                href="/terms"
                className="font-sans text-[11px] text-cream/30 hover:text-white uppercase tracking-widest transition-colors"
              >
                Terms of Service
              </Link>
              <Link
                href="/privacy"
                className="font-sans text-[11px] text-cream/30 hover:text-white uppercase tracking-widest transition-colors"
              >
                Cookies
              </Link>
            </div>
          </div>

          {/* Subtle watermarked giant logo */}
          <div className="w-full overflow-hidden flex justify-center mt-12 pointer-events-none select-none">
            <h1 className="font-serif text-[12vw] sm:text-[14vw] md:text-[16vw] font-bold leading-none tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-white/[0.04] to-transparent">
              ETHERIA
            </h1>
          </div>
        </div>
      </div>

      {/* Required keyframes for tailwind animate- shine */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes shine {
          0% { transform: translateX(-150%) skewX(-45deg); }
          100% { transform: translateX(150%) skewX(-45deg); }
        }
      `,
        }}
      />
    </footer>
  );
}
