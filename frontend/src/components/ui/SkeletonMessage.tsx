'use client';

import React from 'react';

function SkeletonLine({ width, height = 12 }: { width: string; height?: number }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 6,
        background:
          'linear-gradient(90deg, rgba(26,46,32,0.06) 25%, rgba(26,46,32,0.12) 50%, rgba(26,46,32,0.06) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s infinite',
      }}
    />
  );
}

function SkeletonBubble({ isUser }: { isUser: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        padding: '0 20px',
        gap: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          alignItems: 'flex-start',
          gap: 12,
          width: '100%',
          maxWidth: 820,
        }}
      >
        {!isUser && (
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'rgba(26,46,32,0.08)',
              flexShrink: 0,
              marginTop: 4,
            }}
          />
        )}
        <div
          style={{
            maxWidth: isUser ? '60%' : '70%',
            padding: isUser ? '12px 16px' : '4px 0',
            borderRadius: isUser ? 16 : 0,
            background: isUser ? 'rgba(26,46,32,0.06)' : 'transparent',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            width: isUser ? '60%' : '70%',
          }}
        >
          <SkeletonLine width="100%" />
          <SkeletonLine width="85%" />
          {!isUser && <SkeletonLine width="70%" />}
        </div>
      </div>
    </div>
  );
}

export default function SkeletonMessage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '16px 0' }}>
      <SkeletonBubble isUser />
      <SkeletonBubble isUser={false} />
      <SkeletonBubble isUser />
      <SkeletonBubble isUser={false} />
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
