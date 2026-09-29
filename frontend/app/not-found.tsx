'use client';

import Link from 'next/link';
import Image from 'next/image';

/* styles only — no LostOrb component */

/* ═══════════════════════════════════════════════════
   404 Page
═══════════════════════════════════════════════════ */
export default function NotFound() {
  return (
    <div
      style={{
        height: '100vh',
        background: '#162a1c',
        fontFamily: 'var(--font-sans)',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* ── Mesh gradient background — same DNA as homepage hero ── */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {/* Primary central glow */}
        <div
          style={{
            position: 'absolute',
            top: '-20%',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '90vw',
            height: '90vw',
            maxWidth: '900px',
            maxHeight: '900px',
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(255,255,255,0.07) 0%, rgba(68,199,103,0.18) 25%, transparent 60%)',
            filter: 'blur(90px)',
            mixBlendMode: 'screen',
            opacity: 0.7,
          }}
        />
        {/* Bottom-right accent */}
        <div
          style={{
            position: 'absolute',
            bottom: '-25%',
            right: '-10%',
            width: '65vw',
            height: '65vw',
            maxWidth: '700px',
            maxHeight: '700px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(68,199,103,0.12) 0%, transparent 68%)',
            filter: 'blur(80px)',
            mixBlendMode: 'screen',
          }}
        />
        {/* Top-left accent */}
        <div
          style={{
            position: 'absolute',
            top: '30%',
            left: '-18%',
            width: '55vw',
            height: '55vw',
            maxWidth: '580px',
            maxHeight: '580px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(46,125,107,0.1) 0%, transparent 68%)',
            filter: 'blur(70px)',
            mixBlendMode: 'screen',
          }}
        />
        {/* Subtle noise overlay — dark texture */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.015) 2px, rgba(0,0,0,0.015) 4px)',
            pointerEvents: 'none',
          }}
        />
      </div>

      {/* ── Top nav bar ── */}
      <header
        style={{
          position: 'relative',
          zIndex: 10,
          padding: '22px 32px',
          display: 'flex',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        <Link href="/">
          <Image
            src="/logo-light.png"
            alt="Etheria"
            width={100}
            height={28}
            style={{ height: 28, width: 'auto', objectFit: 'contain' }}
          />
        </Link>
      </header>

      {/* ── Main content ── */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 24px 80px',
          position: 'relative',
          zIndex: 10,
          textAlign: 'center',
        }}
      >
        {/* Giant 404 */}
        <div
          className="hero-404 fade-up-3"
          style={{
            fontFamily: 'var(--font-flare)',
            fontSize: 'clamp(100px, 22vw, 220px)',
            fontWeight: 400,
            background: 'linear-gradient(135deg, #6ddb8a 0%, #44c767 50%, #2ebd55 100%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            color: 'transparent',
            lineHeight: 0.88,
            letterSpacing: '-0.04em',
            textTransform: 'uppercase',
            marginBottom: 32,
            userSelect: 'none',
          }}
        >
          <span className="hero-404-inner">404</span>
        </div>

        {/* Message */}
        <h1
          className="fade-up-4"
          style={{
            fontFamily: 'var(--font-flare)',
            fontSize: 'clamp(20px, 3.5vw, 36px)',
            fontWeight: 400,
            color: 'rgba(232,228,219,0.70)',
            lineHeight: 1.25,
            letterSpacing: '-0.02em',
            fontStyle: 'italic',
            marginBottom: 16,
            maxWidth: 560,
          }}
        >
          This page seems to have gone off the grid.
        </h1>

        <p
          className="fade-up-4"
          style={{
            fontSize: 14,
            color: 'rgba(232,228,219,0.38)',
            lineHeight: 1.7,
            fontWeight: 300,
            maxWidth: 380,
            marginBottom: 42,
          }}
        >
          The address you&apos;re looking for doesn&apos;t exist or was moved. Your health journey
          continues — let&apos;s get you back on track.
        </p>

        {/* CTAs */}
        <div
          className="fade-up-5"
          style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}
        >
          <Link
            href="/"
            className="cta-home"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '13px 28px',
              borderRadius: 40,
              background: '#44c767',
              color: '#0f1f12',
              fontSize: 14,
              fontWeight: 500,
              fontFamily: 'var(--font-sans)',
              textDecoration: 'none',
              letterSpacing: '0.01em',
              boxShadow: '0 4px 20px rgba(68,199,103,0.25)',
            }}
          >
            ← Back to Home
          </Link>
          <Link
            href="/dashboard"
            className="cta-back"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '13px 28px',
              borderRadius: 40,
              border: '1px solid rgba(232,228,219,0.22)',
              color: 'rgba(232,228,219,0.70)',
              fontSize: 14,
              fontWeight: 400,
              fontFamily: 'var(--font-sans)',
              textDecoration: 'none',
              letterSpacing: '0.01em',
              backdropFilter: 'blur(6px)',
            }}
          >
            Open Dashboard
          </Link>
        </div>

        {/* Divider + tagline */}
        <div
          className="fade-up-5"
          style={{
            marginTop: 36,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            opacity: 0.3,
            maxWidth: 340,
            width: '100%',
          }}
        >
          <div style={{ flex: 1, height: 1, background: 'rgba(232,228,219,0.3)' }} />
          <span
            style={{
              fontSize: 11,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: '#e8e4db',
              whiteSpace: 'nowrap',
            }}
          >
            Etheria · AI Health Assistant
          </span>
          <div style={{ flex: 1, height: 1, background: 'rgba(232,228,219,0.3)' }} />
        </div>
      </main>

      {/* ── Large editorial 404 watermark at bottom ── */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: '-4%',
          left: '50%',
          transform: 'translateX(-50%)',
          fontFamily: 'var(--font-flare)',
          fontSize: 'clamp(160px, 35vw, 420px)',
          fontWeight: 400,
          color: 'transparent',
          WebkitTextStroke: '1px rgba(232,228,219,0.04)',
          lineHeight: 1,
          letterSpacing: '-0.05em',
          textTransform: 'uppercase',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          userSelect: 'none',
          zIndex: 1,
        }}
      >
        404
      </div>
    </div>
  );
}
