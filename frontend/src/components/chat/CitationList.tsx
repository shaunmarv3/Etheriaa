'use client';

import React, { useState } from 'react';
import type { Citation } from '../../lib/types';

interface CitationListProps {
  citations: Citation[];
}

const SOURCE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  pubmed: { bg: 'rgba(59,130,246,0.08)', text: '#3b82f6', label: 'PubMed' },
  medlineplus: { bg: 'rgba(168,85,247,0.08)', text: '#a855f7', label: 'MedlinePlus' },
  curated: { bg: 'rgba(71,85,105,0.08)', text: '#475569', label: 'Curated' },
  user_document: { bg: 'rgba(68,199,103,0.08)', text: '#16a34a', label: 'Your Doc' },
  neo4j: { bg: 'rgba(234,179,8,0.08)', text: '#ca8a04', label: 'Graph' },
};

export default function CitationList({ citations }: CitationListProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 11,
          color: '#999',
          padding: 0,
          fontFamily: 'var(--font-sans)',
        }}
      >
        <svg
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
        {citations.length} source{citations.length !== 1 ? 's' : ''}
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div
          style={{
            marginTop: 6,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {citations.map((c, i) => {
            const sc = SOURCE_COLORS[c.source] ?? {
              bg: 'rgba(100,100,100,0.08)',
              text: '#888',
              label: c.source,
            };
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '6px 10px',
                  borderRadius: 8,
                  background: '#fafaf8',
                  border: '1px solid rgba(26,46,32,0.04)',
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    padding: '1px 6px',
                    borderRadius: 5,
                    background: sc.bg,
                    color: sc.text,
                    flexShrink: 0,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {sc.label}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 11.5,
                        color: '#3b82f6',
                        textDecoration: 'none',
                        lineHeight: 1.4,
                      }}
                    >
                      {c.title || c.identifier}
                    </a>
                  ) : (
                    <span
                      style={{
                        fontSize: 11.5,
                        color: '#555',
                        lineHeight: 1.4,
                      }}
                    >
                      {c.title || c.identifier}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
