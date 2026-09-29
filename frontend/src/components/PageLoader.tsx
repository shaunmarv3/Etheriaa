'use client';

import { useEffect, useState } from 'react';

interface PageLoaderProps {
  onComplete?: () => void;
}

export default function PageLoader({ onComplete }: PageLoaderProps) {
  const [visible, setVisible] = useState(true);
  const [phase, setPhase] = useState<'loading' | 'exiting'>('loading');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Play the intro once per browser session, not on every full page load.
    try {
      if (sessionStorage.getItem('etheria-intro-seen')) {
        // Deferred: the first render (server and client) always shows the loader.
        const t = setTimeout(() => {
          setVisible(false);
          onComplete?.();
        }, 0);
        return () => clearTimeout(t);
      }
      sessionStorage.setItem('etheria-intro-seen', '1');
    } catch {
      // storage unavailable: play the intro
    }
    const duration = 2000;
    const interval = 20;
    const steps = duration / interval;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      const easeOutQuart = 1 - Math.pow(1 - currentStep / steps, 4);
      setProgress(Math.min(easeOutQuart * 100, 100));

      if (currentStep >= steps) {
        clearInterval(timer);
        setPhase('exiting');
        setTimeout(() => {
          setVisible(false);
          onComplete?.();
        }, 800);
      }
    }, interval);

    return () => clearInterval(timer);
  }, [onComplete]);

  if (!visible) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] bg-[#0c130f] text-cream flex flex-col items-center justify-center transition-all duration-[800ms] ease-[cubic-bezier(0.76,0,0.24,1)] ${
        phase === 'exiting'
          ? 'opacity-0 scale-[1.02] pointer-events-none blur-sm'
          : 'opacity-100 scale-100 blur-none'
      }`}
    >
      <div className="relative w-full max-w-sm flex flex-col items-center px-6">
        {/* Subtle background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-[#44c767] rounded-full blur-[120px] opacity-[0.08] pointer-events-none" />

        {/* EKG Heartbeat Animation */}
        <div className="relative mb-12 w-48 h-20 flex items-center justify-center">
          <svg viewBox="0 0 200 100" fill="none" className="w-full h-full overflow-visible">
            {/* Background faint line */}
            <path
              d="M 0 50 L 50 50 L 65 20 L 85 95 L 105 10 L 125 75 L 140 50 L 200 50"
              stroke="#44c767"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="opacity-10"
            />
            {/* Animated bright line */}
            <path
              d="M 0 50 L 50 50 L 65 20 L 85 95 L 105 10 L 125 75 L 140 50 L 200 50"
              stroke="#44c767"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="450"
              strokeDashoffset="450"
              style={{ animation: 'ekg-draw 2.5s cubic-bezier(0.4, 0, 0.2, 1) infinite' }}
              className="drop-shadow-[0_0_12px_rgba(68,199,103,1)]"
            />
          </svg>

          {/* Pulsing signal dot at the end of the line */}
          <div className="absolute right-0 top-[37px] w-2 h-2 bg-[#44c767] rounded-full shadow-[0_0_15px_rgba(68,199,103,1)] animate-[ping_2.5s_infinite]" />
        </div>

        {/* Wordmark */}
        <h1 className="font-serif text-[clamp(2.5rem,5vw,3.5rem)] tracking-tight uppercase mb-3 text-cream opacity-90 drop-shadow-sm font-light">
          Etheria
        </h1>

        {/* Eyebrow / Tagline */}
        <div className="font-sans text-[10px] sm:text-xs uppercase tracking-[0.25em] text-cream/30 mb-14 flex items-center gap-4">
          <span className="w-6 h-[1px] bg-gradient-to-r from-transparent to-cream/20" />
          AI Health Assistant
          <span className="w-6 h-[1px] bg-gradient-to-l from-transparent to-cream/20" />
        </div>

        {/* Precision Progress Bar */}
        <div className="relative w-64 h-[2px] bg-white/5 rounded-full overflow-hidden">
          <div
            className="absolute top-0 left-0 h-full bg-[#44c767] shadow-[0_0_10px_rgba(68,199,103,0.5)] transition-all duration-[20ms] ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Progress Percentage */}
        <div className="mt-4 font-sans text-[10px] tracking-widest text-[#44c767]/60 font-medium">
          {Math.floor(progress)}%
        </div>
      </div>

      {/* Required keyframes for drawing animation */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes ekg-draw {
          0% { stroke-dashoffset: 450; opacity: 0; }
          15% { opacity: 1; }
          50% { stroke-dashoffset: 0; }
          85% { opacity: 1; }
          100% { stroke-dashoffset: -450; opacity: 0; }
        }
      `,
        }}
      />
    </div>
  );
}
