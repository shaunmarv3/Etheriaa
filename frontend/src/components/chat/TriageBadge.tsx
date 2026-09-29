'use client';

import React from 'react';
import type { TriageLevel } from '../../lib/types';

interface TriageBadgeProps {
  level: TriageLevel;
}

const CONFIG: Record<
  TriageLevel,
  { bg: string; border: string; text: string; dot: string; label: string }
> = {
  RED: {
    bg: 'rgba(220,38,38,0.08)',
    border: 'rgba(220,38,38,0.25)',
    text: '#dc2626',
    dot: '#dc2626',
    label: 'EMERGENCY',
  },
  YELLOW: {
    bg: 'rgba(234,179,8,0.08)',
    border: 'rgba(234,179,8,0.25)',
    text: '#ca8a04',
    dot: '#eab308',
    label: 'SEE A DOCTOR',
  },
  GREEN: {
    bg: 'rgba(68,199,103,0.08)',
    border: 'rgba(68,199,103,0.25)',
    text: '#16a34a',
    dot: '#44c767',
    label: 'LOW',
  },
};

export default function TriageBadge({ level }: TriageBadgeProps) {
  const c = CONFIG[level];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 10px',
        borderRadius: 20,
        background: c.bg,
        border: `1px solid ${c.border}`,
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '0.06em',
        color: c.text,
        textTransform: 'uppercase',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: c.dot,
          flexShrink: 0,
        }}
      />
      {c.label}
    </span>
  );
}
