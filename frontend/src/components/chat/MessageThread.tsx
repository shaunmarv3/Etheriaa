'use client';

import React, { useEffect, useRef } from 'react';
import type { Message } from '../../lib/types';
import TriageBadge from './TriageBadge';
import DifferentialSection from './DifferentialSection';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CitationList from './CitationList';
import MessageActions from './MessageActions';
import { IconAlert } from '../ui/Icons';
import RAGProgress from './RAGProgress';
import AgentFlowPanel from './AgentFlowPanel';
import SkeletonMessage from '../ui/SkeletonMessage';

/* ── Mini orb avatar (scaled-down version of the dashboard EtheriaOrb) ─── */
function MiniOrb() {
  return (
    <div style={{ position: 'relative', width: 32, height: 32, flexShrink: 0 }}>
      {/* Glow */}
      <div
        style={{
          position: 'absolute',
          inset: -6,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(68,199,103,0.4) 0%, rgba(68,199,103,0.1) 50%, transparent 70%)',
          filter: 'blur(6px)',
          animation: 'orb-glow-pulse 3s ease-in-out infinite',
        }}
      />
      {/* Sphere */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background:
            'radial-gradient(circle at 34% 28%, rgba(255,255,255,0.95) 0%, rgba(210,255,220,0.88) 13%, rgba(68,199,103,0.90) 36%, rgba(26,92,74,0.95) 63%, rgba(16,44,24,1) 85%, rgba(8,24,13,1) 100%)',
          boxShadow:
            'inset -4px -4px 7px rgba(0,0,0,0.4), inset 2px 2px 5px rgba(255,255,255,0.2), 0 4px 14px rgba(68,199,103,0.35)',
          overflow: 'hidden',
          animation: 'orb-breathe 3s ease-in-out infinite',
        }}
      >
        {/* Specular highlight */}
        <div
          style={{
            position: 'absolute',
            top: 4,
            left: 5,
            width: 9,
            height: 5,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.65)',
            filter: 'blur(1.5px)',
            transform: 'rotate(-28deg)',
          }}
        />
      </div>
    </div>
  );
}

const SIZE_SCALE: Record<string, number> = { sm: 0.88, md: 1, lg: 1.15 };

interface MessageThreadProps {
  messages: Message[];
  isStreaming: boolean;
  isLoadingSession?: boolean;
  textSize?: 'sm' | 'md' | 'lg';
  lastUserMessage?: string | null;
  /** Latest backend `status` event while the reply has no tokens yet. */
  status?: string | null;
  onFollowUpClick?: (question: string) => void;
  onRegenerate?: (message: Message) => void;
}

export default function MessageThread({
  messages,
  isStreaming,
  isLoadingSession,
  textSize = 'md',
  lastUserMessage,
  status,
  onFollowUpClick,
  onRegenerate,
}: MessageThreadProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevMessageCount = useRef(0);
  const userScrolledUp = useRef(false);
  const scale = SIZE_SCALE[textSize] ?? 1;

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    userScrolledUp.current = distanceFromBottom > 80;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const newMessageAdded = messages.length > prevMessageCount.current;
    prevMessageCount.current = messages.length;
    if (newMessageAdded) userScrolledUp.current = false;
    if (newMessageAdded || !userScrolledUp.current) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [messages, isStreaming]);

  if (isLoadingSession) {
    return (
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        <SkeletonMessage />
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(26,46,32,0.25)',
          fontSize: 13 * scale,
          fontFamily: 'var(--font-sans)',
          padding: '0 20px',
          textAlign: 'center',
        }}
      >
        Your conversation will appear here. Start by describing your symptoms.
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="etheria-chat-scroll"
      style={{
        flex: 1,
        width: '100%',
        minHeight: 0,
        overflowY: 'auto',
        padding: '16px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(26,46,32,0.15) transparent',
      }}
    >
      <style>{`
        .etheria-chat-scroll::-webkit-scrollbar { width: 6px; }
        .etheria-chat-scroll::-webkit-scrollbar-track { background: transparent; }
        .etheria-chat-scroll::-webkit-scrollbar-thumb { background-color: rgba(26,46,32,0.15); border-radius: 10px; }
        .etheria-chat-scroll::-webkit-scrollbar-thumb:hover { background-color: rgba(26,46,32,0.3); }
        .etheria-markdown > *:last-child { margin-bottom: 0 !important; }
        .message-group:hover .message-actions { opacity: 1 !important; }
        @keyframes orb-breathe {
          0%, 100% { transform: scale(1); }
          50%       { transform: scale(1.04); }
        }
        @keyframes orb-glow-pulse {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50%       { opacity: 0.8; transform: scale(1.12); }
        }
      `}</style>

      {/* Only the latest reply can be regenerated (spec 4.8). */}
      {messages.map((msg, idx) => (
        <div
          key={msg.id}
          className="message-group"
          style={{ animationDelay: `${Math.min(idx * 0.03, 0.15)}s` }}
        >
          <MessageBubble
            message={msg}
            scale={scale}
            lastUserMessage={lastUserMessage}
            status={idx === messages.length - 1 ? status : null}
            onFollowUpClick={onFollowUpClick}
            onRegenerate={idx === messages.length - 1 ? onRegenerate : undefined}
          />
        </div>
      ))}
    </div>
  );
}

function MessageBubble({
  message,
  scale,
  lastUserMessage,
  status,
  onFollowUpClick,
  onRegenerate,
}: {
  message: Message;
  scale: number;
  lastUserMessage?: string | null;
  status?: string | null;
  onFollowUpClick?: (q: string) => void;
  onRegenerate?: (message: Message) => void;
}) {
  const isUser = message.role === 'user';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        padding: '0 20px',
        width: '100%',
        margin: '0 auto',
        maxWidth: 820,
        gap: 4,
      }}
    >
      {/* Row: avatar + bubble */}
      <div
        style={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          alignItems: 'flex-start',
          gap: 10,
          width: '100%',
        }}
      >
        {/* Avatar — 3D orb */}
        {!isUser && <MiniOrb />}

        <div
          style={{
            maxWidth: isUser ? '78%' : 'calc(100% - 44px)',
            padding: isUser ? '10px 15px' : '2px 0',
            borderRadius: isUser ? '16px 16px 2px 16px' : '0px',
            background: isUser ? '#1a2e20' : 'transparent',
            color: isUser ? '#e8e4db' : '#1a1a1a',
            fontSize: 14.5 * scale,
            lineHeight: 1.65,
            fontFamily: 'var(--font-sans)',
            boxShadow: isUser ? '0 3px 14px rgba(22,42,28,0.2)' : 'none',
            wordBreak: 'break-word' as const,
          }}
        >
          {/* Triage badge — medical responses only */}
          {!isUser && message.triageLevel && message.agentTrace?.intent !== 'off_topic' && (
            <div style={{ marginBottom: 12 }}>
              <TriageBadge level={message.triageLevel} />
            </div>
          )}

          {/* Emergency prefix for RED triage */}
          {!isUser &&
            message.triageLevel === 'RED' &&
            message.agentTrace?.intent !== 'off_topic' && (
              <div
                style={{
                  padding: '10px 14px',
                  marginBottom: 14,
                  borderRadius: 10,
                  background: 'rgba(220,38,38,0.06)',
                  border: '1px solid rgba(220,38,38,0.18)',
                  fontSize: 13 * scale,
                  fontWeight: 600,
                  color: '#dc2626',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  lineHeight: 1.5,
                }}
              >
                <IconAlert size={16} color="#dc2626" style={{ marginTop: -1, flexShrink: 0 }} />
                <span>
                  This may be a medical emergency. Call 112 now, or 108 for an ambulance. Do not
                  wait.
                </span>
              </div>
            )}

          {/* Agent flow panel — medical responses only */}
          {!isUser &&
            !message.isStreaming &&
            message.agentTrace &&
            message.agentTrace.intent !== 'off_topic' &&
            (message.agentTrace.agents?.length ?? 0) > 0 && (
              <AgentFlowPanel trace={message.agentTrace} level={message.triageLevel} />
            )}

          {/* Message content or RAG progress */}
          <div
            style={{ letterSpacing: '0.01em' }}
            className={`etheria-markdown${!isUser && message.isStreaming && message.content ? ' etheria-streaming' : ''}`}
          >
            {!isUser && message.content === '' && message.isStreaming ? (
              <RAGProgress status={status} />
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ node: _node, ...props }) => (
                    <p
                      style={{
                        margin: '0 0 14px',
                        lineHeight: 1.75,
                        color: isUser ? '#e8e4db' : '#2d2d2d',
                        fontSize: 14 * scale,
                      }}
                      {...props}
                    />
                  ),
                  strong: ({ node: _node, ...props }) => (
                    <strong
                      style={{
                        fontWeight: 700,
                        color: isUser ? '#fff' : '#1a2e20',
                        background: isUser ? 'rgba(255,255,255,0.12)' : 'rgba(68,199,103,0.12)',
                        padding: '1px 5px',
                        borderRadius: 4,
                      }}
                      {...props}
                    />
                  ),
                  em: ({ node: _node, ...props }) => (
                    <em
                      style={{
                        fontStyle: 'normal',
                        color: isUser ? '#c8f5d5' : '#16a34a',
                        fontWeight: 500,
                      }}
                      {...props}
                    />
                  ),
                  ul: ({ node: _node, ...props }) => (
                    <ul
                      style={{
                        margin: '0 0 14px',
                        paddingLeft: 0,
                        listStyle: 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                      {...props}
                    />
                  ),
                  ol: ({ node: _node, ...props }) => (
                    <ol
                      style={{
                        margin: '0 0 14px',
                        paddingLeft: 0,
                        listStyle: 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                        counterReset: 'item',
                      }}
                      {...props}
                    />
                  ),
                  li: ({
                    node: _node,
                    ...props
                  }: {
                    node?: unknown;
                    children?: React.ReactNode;
                  }) => (
                    <li
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 8,
                        padding: '7px 10px',
                        borderRadius: 8,
                        background: isUser ? 'rgba(255,255,255,0.07)' : 'rgba(26,46,32,0.04)',
                        border: isUser
                          ? '1px solid rgba(255,255,255,0.08)'
                          : '1px solid rgba(26,46,32,0.06)',
                        fontSize: 13.5 * scale,
                        lineHeight: 1.6,
                        color: isUser ? '#e8e4db' : '#2d2d2d',
                      }}
                    >
                      <span
                        style={{
                          flexShrink: 0,
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: isUser ? 'rgba(255,255,255,0.5)' : '#44c767',
                          marginTop: 7,
                        }}
                      />
                      <span {...props} />
                    </li>
                  ),
                  h1: ({ node: _node, ...props }) => (
                    <div style={{ margin: '18px 0 10px' }}>
                      <h1
                        style={{
                          margin: 0,
                          fontSize: 17 * scale,
                          fontWeight: 700,
                          color: isUser ? '#fff' : '#1a2e20',
                          letterSpacing: '-0.02em',
                        }}
                        {...props}
                      />
                      <div
                        style={{
                          marginTop: 6,
                          height: 2,
                          width: 32,
                          borderRadius: 2,
                          background: '#44c767',
                        }}
                      />
                    </div>
                  ),
                  h2: ({ node: _node, ...props }) => (
                    <div
                      style={{
                        margin: '16px 0 8px',
                        paddingLeft: 10,
                        borderLeft: '3px solid #44c767',
                      }}
                    >
                      <h2
                        style={{
                          margin: 0,
                          fontSize: 15 * scale,
                          fontWeight: 600,
                          color: isUser ? '#c8f5d5' : '#1a2e20',
                        }}
                        {...props}
                      />
                    </div>
                  ),
                  h3: ({ node: _node, ...props }) => (
                    <h3
                      style={{
                        margin: '14px 0 6px',
                        fontSize: 13.5 * scale,
                        fontWeight: 600,
                        color: isUser ? '#e8e4db' : '#374151',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                      }}
                      {...props}
                    />
                  ),
                  blockquote: ({ node: _node, ...props }) => (
                    <blockquote
                      style={{
                        margin: '12px 0',
                        padding: '10px 14px',
                        borderRadius: 10,
                        borderLeft: '3px solid #44c767',
                        background: 'rgba(68,199,103,0.06)',
                        fontSize: 13.5 * scale,
                        color: '#374151',
                        fontStyle: 'normal',
                      }}
                      {...props}
                    />
                  ),
                  code: ({
                    className,
                    children,
                    ...props
                  }: {
                    className?: string;
                    children?: React.ReactNode;
                  }) => {
                    const isBlock = className?.startsWith('language-');
                    return isBlock ? (
                      <pre
                        style={{
                          margin: '10px 0',
                          padding: '12px 14px',
                          borderRadius: 10,
                          background: 'rgba(26,46,32,0.07)',
                          fontSize: 12.5 * scale,
                          overflowX: 'auto',
                          fontFamily: 'monospace',
                          color: '#1a2e20',
                          border: '1px solid rgba(26,46,32,0.1)',
                        }}
                      >
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    ) : (
                      <code
                        style={{
                          padding: '1px 6px',
                          borderRadius: 5,
                          background: isUser ? 'rgba(255,255,255,0.15)' : 'rgba(26,46,32,0.08)',
                          fontSize: '0.88em',
                          fontFamily: 'monospace',
                          color: isUser ? '#c8f5d5' : '#16a34a',
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                  a: ({ node: _node, ...props }) => (
                    <a
                      style={{
                        color: '#44c767',
                        textDecoration: 'underline',
                        textUnderlineOffset: 2,
                      }}
                      target="_blank"
                      rel="noopener noreferrer"
                      {...props}
                    />
                  ),
                  hr: () => (
                    <hr
                      style={{
                        margin: '16px 0',
                        border: 'none',
                        borderTop: '1px solid rgba(26,46,32,0.1)',
                      }}
                    />
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </div>

          {/* Differential diagnoses */}
          {!isUser && message.differential && message.differential.length > 0 && (
            <DifferentialSection differentials={message.differential} />
          )}

          {/* Citations */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <CitationList citations={message.citations} />
            </div>
          )}
        </div>
      </div>

      {/* Follow-up questions — vertical list */}
      {!isUser &&
        message.followUpQuestions &&
        message.followUpQuestions.length > 0 &&
        !message.isStreaming && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingLeft: 44 }}>
            {message.followUpQuestions.map((q: string, i: number) => (
              <button
                key={i}
                className="followup-btn"
                onClick={() => onFollowUpClick?.(q)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 14px',
                  borderRadius: 10,
                  border: '1px solid rgba(68,199,103,0.18)',
                  background: 'rgba(68,199,103,0.04)',
                  fontSize: 12 * scale,
                  color: '#16a34a',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: 'fit-content',
                  maxWidth: '100%',
                  fontFamily: 'var(--font-sans)',
                  animationDelay: `${i * 0.06}s`,
                }}
                onMouseEnter={(e) => {
                  const b = e.currentTarget as HTMLButtonElement;
                  b.style.background = 'rgba(68,199,103,0.1)';
                  b.style.borderColor = 'rgba(68,199,103,0.35)';
                }}
                onMouseLeave={(e) => {
                  const b = e.currentTarget as HTMLButtonElement;
                  b.style.background = 'rgba(68,199,103,0.04)';
                  b.style.borderColor = 'rgba(68,199,103,0.18)';
                }}
              >
                <svg
                  width="11"
                  height="11"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ flexShrink: 0, opacity: 0.6 }}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                {q.replace(/\*\*/g, '').replace(/\*/g, '')}
              </button>
            ))}
          </div>
        )}

      {/* Message actions (hover-reveal) */}
      {!message.isStreaming && <MessageActions message={message} onRegenerate={onRegenerate} />}

      {/* Timestamp */}
      <span
        style={{
          fontSize: 10 * scale,
          color: 'rgba(26,46,32,0.25)',
          padding: isUser ? '0 4px' : '0 4px 0 44px',
          fontFamily: 'var(--font-sans)',
          whiteSpace: 'nowrap',
        }}
      >
        {new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
}
