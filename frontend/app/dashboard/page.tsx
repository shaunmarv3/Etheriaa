'use client';

import { useAuth, useClerk, useUser, useSession } from '../../src/lib/auth';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useStore } from '../../src/lib/store';
import {
  errorMessage,
  fetchSessionDetail,
  regenerateResponse,
  streamChat,
} from '../../src/lib/api';
import type { Message } from '../../src/lib/types';
import MessageThread from '../../src/components/chat/MessageThread';

/* ═══════════════════════════════════════════════════
   ANIMATIONS — orb + entrance
═══════════════════════════════════════════════════ */
const KEYFRAMES = `
  @keyframes orb-entrance {
    0%   { opacity: 0; transform: scale(0.8); }
    100% { opacity: 1; transform: scale(1);   }
  }
  @keyframes orb-breathe {
    0%, 100% { transform: scale(1);    }
    50%      { transform: scale(1.04); }
  }
  @keyframes orb-glow-pulse {
    0%, 100% { opacity: 0.5; transform: scale(1);    }
    50%      { opacity: 0.8; transform: scale(1.12);  }
  }
  @keyframes fade-slide-up {
    0%   { opacity: 0; transform: translateY(12px); }
    100% { opacity: 1; transform: translateY(0);    }
  }
  @keyframes greeting-word {
    0%   { opacity: 0; transform: translateY(6px); }
    100% { opacity: 1; transform: translateY(0);   }
  }
  @keyframes typing-bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
    40%           { transform: translateY(-5px); opacity: 1; }
  }
`;

/* ═══════════════════════════════════════════════════
   ORB — 3D sphere with breathing animation
═══════════════════════════════════════════════════ */
function EtheriaOrb() {
  return (
    <div
      style={{
        position: 'relative',
        width: 80,
        height: 80,
        animation: 'orb-entrance 400ms ease-out forwards',
      }}
    >
      {/* Glow */}
      <div
        style={{
          position: 'absolute',
          inset: -28,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(68,199,103,0.45) 0%, rgba(68,199,103,0.12) 40%, transparent 68%)',
          filter: 'blur(18px)',
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
            'inset -10px -10px 18px rgba(0,0,0,0.4), inset 6px 6px 14px rgba(255,255,255,0.2), 0 16px 44px rgba(68,199,103,0.35), 0 4px 16px rgba(68,199,103,0.18)',
          overflow: 'hidden',
          animation: 'orb-breathe 3s ease-in-out infinite',
        }}
      >
        {/* Specular */}
        <div
          style={{
            position: 'absolute',
            top: 10,
            left: 13,
            width: 24,
            height: 14,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.65)',
            filter: 'blur(4px)',
            transform: 'rotate(-28deg)',
          }}
        />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   ICONS — SVG icon set
═══════════════════════════════════════════════════ */
const Icons = {
  vitals: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  ),
  chat: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  history: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="12 8 12 12 14 14" />
      <path d="M3.05 11a9 9 0 1 0 .5-4.5" />
      <polyline points="3 3 3 7 7 7" />
    </svg>
  ),
  docs: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  settings: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  help: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  sparkle: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2L9.09 9.09 2 12l7.09 2.91L12 22l2.91-7.09L22 12l-7.09-2.91z" />
    </svg>
  ),
  send: () => (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  ),
  paperclip: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  ),
  mic: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  ),
  plus: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
  stethoscope: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
      <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
      <circle cx="20" cy="10" r="2" />
    </svg>
  ),
};

/* ═══════════════════════════════════════════════════
   NAV ITEMS
═══════════════════════════════════════════════════ */
type NavItem = {
  id: string;
  Icon: () => React.ReactElement;
  label: string;
  href?: string;
  soon?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { id: 'home', Icon: Icons.vitals, label: 'Dashboard' },
  { id: 'chat', Icon: Icons.chat, label: 'New chat' },
  { id: 'history', Icon: Icons.history, label: 'History', href: '/dashboard/history' },
  { id: 'docs', Icon: Icons.docs, label: 'Documents', href: '/dashboard/upload' },
];

/* ═══════════════════════════════════════════════════
   PROMPT CARDS
═══════════════════════════════════════════════════ */
const PROMPT_CARDS = [
  {
    text: 'I have a persistent headache and feel dizzy',
    icon: () => (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#2e7d6b"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path
          d="M12 2a5 5 0 0 0-5 5c0 2.76 2.24 5 5 5s5-2.24 5-5a5 5 0 0 0-5-5z"
          opacity="0.3"
          fill="rgba(68,199,103,0.1)"
        />
        <circle cx="12" cy="8" r="6" />
        <path d="M9.5 8h5" />
        <path d="M12 5.5v5" />
        <path d="M8 14s-3 1.5-3 4v2h14v-2c0-2.5-3-4-3-4" />
      </svg>
    ),
  },
  {
    text: 'What could cause chest tightness after exercise?',
    icon: () => (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#2e7d6b"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path
          d="M20.42 4.58a5.4 5.4 0 0 0-7.65 0L12 5.34l-.77-.76a5.4 5.4 0 0 0-7.65 0 5.4 5.4 0 0 0 0 7.65L12 20.66l8.42-8.42a5.4 5.4 0 0 0 0-7.66z"
          opacity="0.15"
          fill="rgba(68,199,103,0.15)"
        />
        <path d="M20.42 4.58a5.4 5.4 0 0 0-7.65 0L12 5.34l-.77-.76a5.4 5.4 0 0 0-7.65 0 5.4 5.4 0 0 0 0 7.65L12 20.66l8.42-8.42a5.4 5.4 0 0 0 0-7.66z" />
        <polyline points="6 13 9 13 10 11 12 15 14 11 15 13 18 13" />
      </svg>
    ),
  },
  {
    text: 'Explain common symptoms of seasonal allergies',
    icon: () => (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#2e7d6b"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 22V8" />
        <path d="M5 12c0-3 2.5-5 7-5s7 2 7 5" opacity="0.15" fill="rgba(68,199,103,0.15)" />
        <path d="M9 5.5C9 3 10.3 2 12 2s3 1 3 3.5" />
        <path d="M7 9c-2-1-3-2-3-4" />
        <path d="M17 9c2-1 3-2 3-4" />
        <path d="M5 14c-2 0-3.5-.5-4-2" />
        <path d="M19 14c2 0 3.5-.5 4-2" />
        <path d="M12 22c-2 0-4-.5-4-3" />
        <path d="M12 22c2 0 4-.5 4-3" />
      </svg>
    ),
  },
  {
    text: 'Should I be worried about recurring stomach pain?',
    icon: () => (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#2e7d6b"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="9" opacity="0.15" fill="rgba(68,199,103,0.12)" />
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4" />
        <path d="M12 16h.01" />
        <path d="M8 12h1.5c1 0 1.5.5 1.5 1.5S10.5 15 9.5 15H8" />
        <path d="M14.5 12H16v3h-1.5" />
      </svg>
    ),
  },
];

/* ═══════════════════════════════════════════════════
   GREETING HELPER
═══════════════════════════════════════════════════ */
function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good Morning';
  if (h < 17) return 'Good Afternoon';
  return 'Good Evening';
}

/* ═══════════════════════════════════════════════════
   MAIN DASHBOARD
═══════════════════════════════════════════════════ */
export default function DashboardPage() {
  // useSearchParams needs a Suspense boundary for the static build.
  return (
    <Suspense fallback={null}>
      <Dashboard />
    </Suspense>
  );
}

function Dashboard() {
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const { session } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeId = searchParams.get('session');

  const [activeId, setActiveId] = useState('home');
  const [inputValue, setInputValue] = useState('');
  const [lastSentMessage, setLastSentMessage] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [inputFocused, setInputFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Chat state from Zustand
  const messages = useStore((s) => s.messages);
  const isStreaming = useStore((s) => s.isStreaming);
  const sessionId = useStore((s) => s.sessionId);
  const addMessage = useStore((s) => s.addMessage);
  const updateLastAssistant = useStore((s) => s.updateLastAssistant);
  const setSessionId = useStore((s) => s.setSessionId);
  const setStreaming = useStore((s) => s.setStreaming);
  const setMessages = useStore((s) => s.setMessages);
  const resetChat = useStore((s) => s.resetChat);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (isLoaded && !isSignedIn) router.push('/sign-in');
  }, [isLoaded, isSignedIn, router]);

  // "Continue chat" from history: /dashboard?session=<id> loads that conversation.
  useEffect(() => {
    if (!isSignedIn || !resumeId || resumeId === useStore.getState().sessionId) return;
    let cancelled = false;
    fetchSessionDetail(resumeId)
      .then((detail) => {
        if (cancelled) return;
        setSessionId(detail.sessionId);
        setMessages(
          detail.messages.map((m) => ({
            id: m.messageId,
            sessionId: detail.sessionId,
            role: m.role,
            content: m.content,
            intent: m.intent ?? undefined,
            symptoms: m.symptoms ?? undefined,
            triageLevel: m.triageLevel ?? undefined,
            citations: m.citations,
            differential: m.differential,
            createdAt: m.createdAt,
          }))
        );
        const lastUser = [...detail.messages].reverse().find((m) => m.role === 'user');
        setLastSentMessage(lastUser?.content ?? null);
      })
      .catch((err) => console.error('Failed to load session:', errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, resumeId, setMessages, setSessionId]);

  const startNewChat = useCallback(() => {
    resetChat();
    setLastSentMessage(null);
    setStatusLine(null);
    if (resumeId) router.replace('/dashboard');
  }, [resetChat, resumeId, router]);

  const resize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || isStreaming) return;

    setLastSentMessage(text);
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.focus();
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      sessionId: sessionId ?? '',
      role: 'user',
      content: text,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMsg);

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      sessionId: sessionId ?? '',
      role: 'assistant',
      content: '',
      isStreaming: true,
      createdAt: new Date().toISOString(),
    };
    addMessage(assistantMsg);
    setStreaming(true);

    try {
      const authToken = (await session?.getToken()) ?? null;
      await streamChat(
        { sessionId: sessionId ?? undefined, message: text },
        {
          onStatus(message: string) {
            setStatusLine(message || null);
          },
          onToken(token: string) {
            setStatusLine(null);
            const current = useStore.getState().messages;
            const last = current[current.length - 1];
            if (last && last.role === 'assistant') {
              updateLastAssistant({ content: last.content + token, isStreaming: true });
            }
          },
          onMetadata(meta) {
            setSessionId(meta.sessionId);
            updateLastAssistant({
              sessionId: meta.sessionId,
              triageLevel: meta.triageLevel,
              symptoms: meta.symptoms,
              followUpQuestions: meta.followUpQuestions,
              differential: meta.differential,
              citations: meta.citations,
              agentTrace: meta.agent_trace,
              isStreaming: false,
            });
          },
          onDone() {
            setStatusLine(null);
            setStreaming(false);
            updateLastAssistant({ isStreaming: false });
          },
          onError(error: string) {
            setStatusLine(null);
            setStreaming(false);
            const current = useStore.getState().messages;
            const last = current[current.length - 1];
            updateLastAssistant({
              content: last?.content || `Error: ${error}`,
              isStreaming: false,
            });
          },
        },
        authToken
      );
    } catch (err) {
      setStreaming(false);
      updateLastAssistant({
        content: 'Sorry, I encountered an error. Please try again.',
        isStreaming: false,
      });
      console.error('Chat stream error:', err);
    }
  }, [
    inputValue,
    isStreaming,
    sessionId,
    addMessage,
    updateLastAssistant,
    setSessionId,
    setStreaming,
    session,
  ]);

  // Regenerate the last reply (spec 4.8): not streamed, the old reply is replaced.
  const handleRegenerate = useCallback(async () => {
    if (!sessionId || isStreaming) return;
    setStreaming(true);
    updateLastAssistant({
      content: '',
      citations: [],
      followUpQuestions: [],
      differential: [],
      agentTrace: undefined,
      isStreaming: true,
    });
    try {
      const r = await regenerateResponse(sessionId);
      updateLastAssistant({
        id: r.messageId,
        content: r.reply,
        triageLevel: r.triageLevel,
        symptoms: r.symptoms,
        followUpQuestions: r.followUpQuestions,
        differential: r.differential,
        citations: r.citations,
        agentTrace: undefined,
        isStreaming: false,
      });
    } catch (err) {
      updateLastAssistant({
        content: `Error: ${errorMessage(err, 'Could not regenerate the reply.')}`,
        isStreaming: false,
      });
    } finally {
      setStreaming(false);
    }
  }, [sessionId, isStreaming, setStreaming, updateLastAssistant]);

  const handleFollowUpClick = useCallback((question: string) => {
    setInputValue(question.replace(/\*\*/g, '').replace(/\*/g, ''));
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
      }
    });
  }, []);

  const handlePromptCardClick = (text: string) => {
    setInputValue(text);
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        resize();
      }
    });
  };

  if (!isLoaded || !isSignedIn) return null;

  const name = user?.firstName || user?.emailAddresses[0]?.emailAddress?.split('@')[0] || 'there';
  const initials = name.slice(0, 2).toUpperCase();

  /* ── Token mapping from design.md ──
     page-bg      → off-white  #f0ede6
     surface      → warm-white #f5f2ec  (main card background)
     border       → rgba(26,46,32, 0.08)
     accent       → bright-green #44c767
     text-primary → dark-text  #1a1a1a
     text-muted   → muted-text #3d3d3d
     text-subtle  → light-text #666666
     CTA-dark     → dark-green #1a2e20
     card-tint    → rgba(68,199,103,0.04)
  */

  return (
    <>
      <style>{KEYFRAMES}</style>
      <div
        style={{
          display: 'flex',
          height: '100vh',
          overflow: 'hidden',
          fontFamily: 'var(--font-sans)',
          /* page-bg: off-white */
          background: '#f0ede6',
          padding: 10,
          gap: 0,
        }}
      >
        {/* ════════════════ SIDEBAR (icon-only, 64px) ════════════════ */}
        <aside
          style={{
            width: 64,
            minWidth: 64,
            height: '100%',
            flexShrink: 0,
            /* surface token */
            background: '#f5f2ec',
            borderRadius: '16px 0 0 16px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 18,
            paddingBottom: 18,
            borderRight: '1px solid rgba(26,46,32,0.06)',
          }}
        >
          {/* Logo mark */}
          <button
            onClick={() => setActiveId('home')}
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 28,
            }}
          >
            <Image
              src="/favicon.ico"
              alt="E"
              width={28}
              height={28}
              style={{ width: 28, height: 28, borderRadius: 6 }}
            />
          </button>

          {/* Nav icons */}
          <nav
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {NAV_ITEMS.map(({ id, Icon, label, href, soon }) => {
              const isActive = activeId === id;
              return (
                <button
                  key={id}
                  onClick={() => {
                    if (soon) return;
                    if (href) router.push(href);
                    else if (id === 'chat') startNewChat();
                    else setActiveId(id);
                  }}
                  title={`${label}${soon ? ' (coming soon)' : ''}`}
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 11,
                    border: 'none',
                    background: isActive ? 'rgba(68,199,103,0.10)' : 'transparent',
                    /* text-muted for inactive, accent for active */
                    color: isActive ? '#44c767' : '#3d3d3d',
                    cursor: soon ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    transition: 'all 0.18s ease',
                    opacity: soon ? 0.4 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive && !soon) {
                      (e.currentTarget as HTMLButtonElement).style.background =
                        'rgba(26,46,32,0.05)';
                      (e.currentTarget as HTMLButtonElement).style.color = '#1a1a1a';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                      (e.currentTarget as HTMLButtonElement).style.color = soon
                        ? '#3d3d3d'
                        : '#3d3d3d';
                    }
                  }}
                >
                  {/* Active left bar indicator */}
                  {isActive && (
                    <span
                      style={{
                        position: 'absolute',
                        left: -11,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: 3,
                        height: 20,
                        borderRadius: '0 2px 2px 0',
                        /* accent: bright-green */
                        background: '#44c767',
                      }}
                    />
                  )}
                  <Icon />
                </button>
              );
            })}
          </nav>

          {/* Bottom icons: help + settings + avatar */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <button
              title="Account"
              onClick={() => router.push('/dashboard/account')}
              style={{
                width: 42,
                height: 42,
                borderRadius: 11,
                border: 'none',
                background: 'transparent',
                color: '#3d3d3d',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.18s',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(26,46,32,0.05)';
                (e.currentTarget as HTMLButtonElement).style.color = '#1a1a1a';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                (e.currentTarget as HTMLButtonElement).style.color = '#3d3d3d';
              }}
            >
              <Icons.settings />
            </button>
            {/* Avatar */}
            <button
              onClick={async () => {
                setSigningOut(true);
                await signOut({ redirectUrl: '/' });
              }}
              disabled={signingOut}
              title={`${name} — click to sign out`}
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                flexShrink: 0,
                background: 'linear-gradient(135deg, rgba(68,199,103,0.25), rgba(26,92,74,0.45))',
                border: '1.5px solid rgba(68,199,103,0.28)',
                color: '#44c767',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
                fontWeight: 600,
                transition: 'all 0.18s',
                marginTop: 4,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(68,199,103,0.55)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(68,199,103,0.28)';
              }}
            >
              {initials}
            </button>
          </div>
        </aside>

        {/* ════════════════ MAIN SURFACE ════════════════ */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            height: '100%',
            /* surface token */
            background: '#f5f2ec',
            borderRadius: '0 16px 16px 0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 8px 32px rgba(0,0,0,0.03)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* ── TOP BAR ── */}

          {/* ── MAIN CONTENT ── */}
          <main
            style={{
              flex: 1,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: hasMessages ? 'flex-start' : 'center',
              padding: hasMessages ? '0' : '0 24px 48px',
              overflowY: hasMessages ? 'hidden' : 'auto',
              overflowX: 'hidden',
              position: 'relative',
            }}
          >
            {/* ── Background glows ── */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: '-10%',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '70%',
                  height: '55%',
                  borderRadius: '50%',
                  background:
                    'radial-gradient(circle, rgba(68,199,103,0.10) 0%, rgba(68,199,103,0.04) 40%, transparent 70%)',
                  filter: 'blur(60px)',
                }}
              />
            </div>

            {/* ── HERO: ORB + GREETING (no messages) ── */}
            {!hasMessages && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: '100%',
                  maxWidth: 680,
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                <div style={{ marginBottom: 28 }}>
                  <EtheriaOrb />
                </div>

                {/* Greeting */}
                <h1
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: 'clamp(28px, 4vw, 44px)',
                    fontWeight: 400,
                    letterSpacing: '-0.02em',
                    color: '#1a1a1a',
                    textAlign: 'center',
                    lineHeight: 1.15,
                    margin: 0,
                    marginBottom: 6,
                    animation: 'fade-slide-up 350ms ease-out forwards',
                  }}
                >
                  {getGreeting()}, {name}
                </h1>
                <p
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: 'clamp(22px, 3vw, 34px)',
                    fontWeight: 400,
                    letterSpacing: '-0.01em',
                    textAlign: 'center',
                    lineHeight: 1.25,
                    margin: 0,
                    marginBottom: 36,
                    fontStyle: 'italic',
                    /* Gradient text: bright-green → teal-green */
                    background: 'linear-gradient(135deg, #44c767, #1a5c4a)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    paddingRight: '0.15em' /* Fix for italic text clip */,
                    animation: 'fade-slide-up 350ms ease-out 100ms both',
                  }}
                >
                  How are you feeling?
                </p>

                {/* ── INPUT BOX ── */}
                <div
                  style={{
                    width: '100%',
                    /* surface: white card */
                    background: '#ffffff',
                    borderRadius: 14,
                    /* border: accent on focus, default border token */
                    border: inputFocused ? '1px solid #44c767' : '1px solid rgba(26,46,32,0.08)',
                    boxShadow: inputFocused
                      ? '0 0 0 3px rgba(68,199,103,0.12), 0 4px 24px rgba(0,0,0,0.06)'
                      : '0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 24px rgba(0,0,0,0.06)',
                    overflow: 'hidden',
                    marginBottom: 14,
                    transition: 'border 0.2s, box-shadow 0.2s',
                    animation: 'fade-slide-up 350ms ease-out 200ms both',
                  }}
                >
                  {/* Textarea row */}
                  <div
                    style={{
                      padding: '16px 18px 12px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                    }}
                  >
                    <span style={{ color: '#44c767', marginTop: 3, flexShrink: 0 }}>
                      <Icons.sparkle />
                    </span>
                    <textarea
                      ref={textareaRef}
                      value={inputValue}
                      onChange={(e) => {
                        setInputValue(e.target.value);
                        resize();
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSend();
                        }
                      }}
                      onFocus={() => setInputFocused(true)}
                      onBlur={() => setInputFocused(false)}
                      placeholder="Describe your symptoms or ask a health question…"
                      rows={1}
                      style={{
                        flex: 1,
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        resize: 'none',
                        /* Body: 15px / 400 */
                        fontSize: 15,
                        color: '#1a1a1a',
                        lineHeight: 1.65,
                        fontFamily: 'var(--font-sans)',
                        minHeight: 60,
                        maxHeight: 160,
                      }}
                    />
                  </div>
                  {/* Toolbar */}
                  <div
                    style={{
                      borderTop: '1px solid rgba(26,46,32,0.05)',
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: 'rgba(26,46,32,0.015)',
                    }}
                  >
                    <div style={{ display: 'flex', gap: 7 }}>
                      <ToolbarPill
                        icon={<Icons.paperclip />}
                        label="Upload a report"
                        onClick={() => router.push('/dashboard/upload')}
                      />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {/* Send */}
                      <button
                        onClick={handleSend}
                        disabled={!inputValue.trim() || isStreaming}
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: 10,
                          border: 'none',
                          /* CTA dark */
                          background: inputValue.trim() ? '#1a2e20' : 'rgba(26,46,32,0.09)',
                          color: inputValue.trim() ? '#44c767' : '#bbb',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: inputValue.trim() ? 'pointer' : 'default',
                          transition: 'all 0.2s',
                          boxShadow: inputValue.trim() ? '0 4px 14px rgba(22,42,28,0.28)' : 'none',
                          flexShrink: 0,
                        }}
                        title="Start Assessment"
                      >
                        <Icons.send />
                      </button>
                    </div>
                  </div>
                </div>

                {/* ── PROMPT CARDS ── */}
                <div
                  style={{
                    width: '100%',
                    animation: 'fade-slide-up 350ms ease-out 300ms both',
                  }}
                >
                  {/* Label */}
                  <p
                    style={{
                      /* Label caps: 11px / 600 / 1px tracking / uppercase */
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: '1px',
                      textTransform: 'uppercase',
                      /* text-subtle: light-text */
                      color: '#666666',
                      marginBottom: 12,
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    Get started with an example below
                  </p>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, 1fr)',
                      gap: 10,
                    }}
                  >
                    {PROMPT_CARDS.map((card, i) => (
                      <button
                        key={i}
                        onClick={() => handlePromptCardClick(card.text)}
                        style={{
                          padding: '14px 14px 16px',
                          borderRadius: 12,
                          /* card-tint: slight green wash */
                          background: 'rgba(68,199,103,0.04)',
                          /* border: border token */
                          border: '1px solid rgba(68,199,103,0.10)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: 16,
                          transition: 'all 0.2s ease',
                          fontFamily: 'var(--font-sans)',
                          minHeight: 110,
                        }}
                        onMouseEnter={(e) => {
                          const b = e.currentTarget as HTMLButtonElement;
                          b.style.borderColor = 'rgba(68,199,103,0.35)';
                          b.style.background = 'rgba(68,199,103,0.08)';
                        }}
                        onMouseLeave={(e) => {
                          const b = e.currentTarget as HTMLButtonElement;
                          b.style.borderColor = 'rgba(68,199,103,0.10)';
                          b.style.background = 'rgba(68,199,103,0.04)';
                        }}
                      >
                        <span
                          style={{
                            /* Small: 13px / 400, text-muted */
                            fontSize: 13,
                            lineHeight: 1.45,
                            color: '#3d3d3d',
                          }}
                        >
                          {card.text}
                        </span>
                        <span style={{ opacity: 0.7 }}>{card.icon()}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Disclaimer */}
                <p
                  style={{
                    fontSize: 11,
                    color: 'rgba(26,46,32,0.28)',
                    textAlign: 'center',
                    lineHeight: 1.65,
                    maxWidth: 460,
                    marginTop: 20,
                    fontFamily: 'var(--font-sans)',
                    animation: 'fade-slide-up 350ms ease-out 400ms both',
                  }}
                >
                  Etheria provides educational health guidance only — not a substitute for
                  professional medical advice. Always consult a qualified healthcare provider.
                </p>
              </div>
            )}

            {/* ── MESSAGE THREAD (chat started) ── */}
            {hasMessages && (
              <div
                style={{
                  width: '100%',
                  flex: '1 1 0',
                  minHeight: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                <MessageThread
                  messages={messages}
                  isStreaming={isStreaming}
                  lastUserMessage={lastSentMessage}
                  status={isStreaming ? statusLine : null}
                  onFollowUpClick={handleFollowUpClick}
                  onRegenerate={handleRegenerate}
                />
              </div>
            )}

            {/* ── CHAT INPUT (chat started) ── */}
            {hasMessages && (
              <div
                style={{
                  width: '100%',
                  maxWidth: 720,
                  marginLeft: 'auto',
                  marginRight: 'auto',
                  padding: '12px 20px 16px',
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    background: '#ffffff',
                    borderRadius: 14,
                    border: inputFocused ? '1px solid #44c767' : '1px solid rgba(26,46,32,0.08)',
                    boxShadow: inputFocused
                      ? '0 0 0 3px rgba(68,199,103,0.12), 0 4px 24px rgba(0,0,0,0.06)'
                      : '0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 24px rgba(0,0,0,0.06)',
                    overflow: 'hidden',
                    transition: 'border 0.2s, box-shadow 0.2s',
                  }}
                >
                  <div
                    style={{
                      padding: '14px 18px 10px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                    }}
                  >
                    <span style={{ color: '#44c767', marginTop: 3, flexShrink: 0 }}>
                      <Icons.sparkle />
                    </span>
                    <textarea
                      ref={textareaRef}
                      value={inputValue}
                      onChange={(e) => {
                        setInputValue(e.target.value);
                        resize();
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSend();
                        }
                      }}
                      onFocus={() => setInputFocused(true)}
                      onBlur={() => setInputFocused(false)}
                      placeholder="Describe your symptoms or ask a health question…"
                      rows={1}
                      disabled={isStreaming}
                      style={{
                        flex: 1,
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        resize: 'none',
                        fontSize: 15,
                        color: '#1a1a1a',
                        lineHeight: 1.65,
                        fontFamily: 'var(--font-sans)',
                        minHeight: 28,
                        maxHeight: 160,
                        opacity: isStreaming ? 0.5 : 1,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      borderTop: '1px solid rgba(26,46,32,0.05)',
                      padding: '9px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      background: 'rgba(26,46,32,0.015)',
                    }}
                  >
                    <button
                      onClick={handleSend}
                      disabled={!inputValue.trim() || isStreaming}
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: 10,
                        border: 'none',
                        background:
                          inputValue.trim() && !isStreaming ? '#1a2e20' : 'rgba(26,46,32,0.09)',
                        color: inputValue.trim() && !isStreaming ? '#44c767' : '#bbb',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: inputValue.trim() && !isStreaming ? 'pointer' : 'default',
                        transition: 'all 0.2s',
                        boxShadow:
                          inputValue.trim() && !isStreaming
                            ? '0 4px 14px rgba(22,42,28,0.28)'
                            : 'none',
                        flexShrink: 0,
                      }}
                      title="Send message"
                    >
                      <Icons.send />
                    </button>
                  </div>
                </div>
                <p
                  style={{
                    fontSize: 10,
                    color: 'rgba(26,46,32,0.22)',
                    textAlign: 'center',
                    marginTop: 8,
                    lineHeight: 1.5,
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  Etheria provides educational health guidance only — not medical advice.
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </>
  );
}

/* ════════════════════════════════
   ToolbarPill — rounded pill buttons in toolbar
════════════════════════════════ */
function ToolbarPill({
  icon,
  label,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={disabled ? `${label} (coming soon)` : label}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 14px',
        /* border-radius: 20px for pill shape */
        borderRadius: 20,
        /* border token */
        border: '1px solid rgba(26,46,32,0.09)',
        background: '#ffffff',
        /* Small: 13px */
        fontSize: 13,
        color: '#666666',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'all 0.15s',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {icon}
      {label}
    </button>
  );
}
