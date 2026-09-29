'use client';

import React, { useState } from 'react';
import type { DifferentialDiagnosis } from '../../lib/types';
import { IconMicroscope } from '../ui/Icons';

interface DifferentialSectionProps {
  differentials: DifferentialDiagnosis[];
}

const LIKELIHOOD_COLORS: Record<string, string> = {
  likely: '#dc2626',
  possible: '#ca8a04',
  unlikely: '#16a34a',
};

export default function DifferentialSection({ differentials }: DifferentialSectionProps) {
  const [expanded, setExpanded] = useState(false);

  if (!differentials || differentials.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 10,
        borderRadius: 12,
        border: '1px solid rgba(26,46,32,0.08)',
        background: 'rgba(255,255,255,0.7)',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '9px 14px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 500,
          color: '#555',
          fontFamily: 'var(--font-sans)',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <IconMicroscope size={14} color="#555" />
          Possible conditions ({differentials.length})
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div style={{ padding: '0 14px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {differentials.map((dx, i) => (
            <div
              key={i}
              style={{
                padding: '10px 12px',
                borderRadius: 10,
                background: '#fafaf8',
                border: '1px solid rgba(26,46,32,0.05)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: '#1a1a1a',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  {dx.condition}
                </span>
                <span
                  style={{
                    fontSize: 9.5,
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: LIKELIHOOD_COLORS[dx.likelihood] ?? '#888',
                    padding: '1px 7px',
                    borderRadius: 10,
                    background: `${LIKELIHOOD_COLORS[dx.likelihood] ?? '#888'}12`,
                  }}
                >
                  {dx.likelihood}
                </span>
              </div>
              <p
                style={{
                  fontSize: 12,
                  color: '#666',
                  lineHeight: 1.5,
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                }}
              >
                {dx.rationale}
              </p>
              {dx.workup && dx.workup.length > 0 && (
                <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {dx.workup.map((w: string, j: number) => (
                    <span
                      key={j}
                      style={{
                        fontSize: 10.5,
                        padding: '2px 8px',
                        borderRadius: 6,
                        background: 'rgba(68,199,103,0.08)',
                        color: '#16a34a',
                        border: '1px solid rgba(68,199,103,0.15)',
                      }}
                    >
                      {w}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
