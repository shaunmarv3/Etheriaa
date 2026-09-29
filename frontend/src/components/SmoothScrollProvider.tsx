'use client';

import { useEffect } from 'react';
import Lenis from 'lenis';

export default function SmoothScrollProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 1.0,
      touchMultiplier: 2,
      // Don't intercept scroll inside elements that have their own overflow scroll
      prevent: (node: Element) => {
        let el: Element | null = node;
        while (el) {
          const style = window.getComputedStyle(el);
          const overflowY = style.overflowY;
          if (
            el !== document.documentElement &&
            el !== document.body &&
            (overflowY === 'auto' || overflowY === 'scroll') &&
            el.scrollHeight > el.clientHeight
          ) {
            return true;
          }
          el = el.parentElement;
        }
        return false;
      },
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }

    requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
    };
  }, []);

  return <>{children}</>;
}
