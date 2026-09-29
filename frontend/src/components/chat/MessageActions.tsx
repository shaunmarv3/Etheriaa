'use client';

import React, { useState } from 'react';
import type { Message } from '../../lib/types';

interface MessageActionsProps {
  message: Message;
  onRegenerate?: (message: Message) => void;
}

export default function MessageActions({ message, onRegenerate }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const isAssistant = message.role === 'assistant';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard not available
    }
  };

  return (
    <>
      <div
        className="message-actions"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          opacity: 0,
          transition: 'opacity 0.15s',
          paddingLeft: isAssistant ? 44 : 0,
          justifyContent: isAssistant ? 'flex-start' : 'flex-end',
        }}
      >
        {/* Copy */}
        <ActionBtn onClick={handleCopy} title={copied ? 'Copied!' : 'Copy'}>
          {copied ? (
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#44c767"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </ActionBtn>

        {/* Regenerate */}
        {isAssistant && onRegenerate && (
          <ActionBtn onClick={() => onRegenerate(message)} title="Regenerate response">
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
          </ActionBtn>
        )}
      </div>
    </>
  );
}

function ActionBtn({
  onClick,
  title,
  children,
  active = false,
  activeColor,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
  active?: boolean;
  activeColor?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 26,
        height: 26,
        borderRadius: 6,
        border: `1px solid ${active ? (activeColor ?? 'rgba(26,46,32,0.15)') + '40' : 'rgba(26,46,32,0.08)'}`,
        background: active ? (activeColor ?? '#16a34a') + '10' : 'transparent',
        color: active ? (activeColor ?? '#16a34a') : 'rgba(26,46,32,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'all 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (!active) (e.currentTarget as HTMLButtonElement).style.color = '#1a2e20';
        (e.currentTarget as HTMLButtonElement).style.background = 'rgba(26,46,32,0.05)';
      }}
      onMouseLeave={(e) => {
        if (!active) (e.currentTarget as HTMLButtonElement).style.color = 'rgba(26,46,32,0.4)';
        (e.currentTarget as HTMLButtonElement).style.background = active
          ? (activeColor ?? '#16a34a') + '10'
          : 'transparent';
      }}
    >
      {children}
    </button>
  );
}
