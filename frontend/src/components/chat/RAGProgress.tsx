'use client';

import React from 'react';

interface RAGProgressProps {
  /** The latest `status` event from the backend (spec 4.7), e.g. "Searching your reports". */
  status?: string | null;
}

/**
 * Typing indicator shown before the first token. It shows only what the backend
 * reports through `status` events; v1's timed, simulated step list is gone.
 */
export default function RAGProgress({ status }: RAGProgressProps) {
  return (
    <>
      <style>{`
        @keyframes rag-pulse {
          0%, 100% { opacity: 0.4; transform: scale(0.85); }
          50%       { opacity: 1;   transform: scale(1);    }
        }
      `}</style>
      <div style={{ padding: '10px 4px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', gap: 5 }}>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#44c767',
                animation: `rag-pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </div>
        {status && (
          <span style={{ fontSize: 13, color: '#666666', fontFamily: 'var(--font-sans)' }}>
            {status}
          </span>
        )}
      </div>
    </>
  );
}
