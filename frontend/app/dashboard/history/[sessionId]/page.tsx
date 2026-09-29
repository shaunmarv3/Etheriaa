'use client';

import { useAuth, useClerk } from '../../../../src/lib/auth';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  fetchSessionDetail,
  deleteSession,
  errorMessage,
  type SessionDetail,
} from '../../../../src/lib/api';
import type { TriageLevel } from '../../../../src/lib/types';

// Message component inline
function MessageBubble({
  role,
  content,
  timestamp,
}: {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}) {
  const isUser = role === 'user';

  const formatTime = (isoString?: string) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser ? 'bg-[#162a1c] text-cream' : 'bg-white border border-black/10 text-dark-text'
        }`}
      >
        {/* Content: assistant replies are markdown, as in the live chat */}
        {isUser ? (
          <div className="font-sans text-[14px] leading-[1.6] whitespace-pre-wrap text-cream">
            {content}
          </div>
        ) : (
          <div className="font-sans text-[14px] leading-[1.6] text-dark-text [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_li]:mb-1 [&_strong]:font-semibold [&_em]:italic">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}

        {/* Timestamp */}
        {timestamp && (
          <div
            className={`mt-2 font-sans text-[10px] ${
              isUser ? 'text-cream/60' : 'text-light-text/60'
            }`}
          >
            {formatTime(timestamp)}
          </div>
        )}
      </div>
    </div>
  );
}

// Triage badge component
function TriageBadge({ level }: { level: TriageLevel }) {
  const config = {
    RED: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      dot: 'bg-red-500',
      text: 'text-red-700',
      label: 'Urgent Care Recommended',
      description:
        'This assessment indicates symptoms that may require immediate medical attention.',
    },
    YELLOW: {
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      dot: 'bg-amber-500',
      text: 'text-amber-700',
      label: 'Schedule Appointment',
      description: 'Consider scheduling an appointment with your healthcare provider.',
    },
    GREEN: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      dot: 'bg-green-500',
      text: 'text-green-700',
      label: 'Self-Care Appropriate',
      description: 'Monitor symptoms and follow self-care recommendations.',
    },
  };

  const c = config[level];

  return (
    <div className={`rounded-xl ${c.bg} border ${c.border} p-4`}>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${c.dot}`} />
        <span className={`font-sans text-[13px] font-semibold ${c.text}`}>{c.label}</span>
      </div>
      <p className={`font-sans text-[12px] ${c.text} mt-1 opacity-80`}>{c.description}</p>
    </div>
  );
}

export default function SessionDetailPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const { signOut } = useClerk();
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if not signed in
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push('/sign-in');
    }
  }, [isLoaded, isSignedIn, router]);

  // Load session details (state is set in the promise callbacks, not the effect body)
  useEffect(() => {
    if (!isSignedIn || !sessionId) return;
    let cancelled = false;
    fetchSessionDetail(sessionId)
      .then((result) => !cancelled && setSession(result))
      .catch((err) => !cancelled && setError(errorMessage(err, 'Failed to load session')))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, sessionId]);

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this conversation? This cannot be undone.')) {
      return;
    }

    setIsDeleting(true);
    setError(null);

    try {
      await deleteSession(sessionId);
      router.push('/dashboard/history');
    } catch (err) {
      setError(errorMessage(err, 'Failed to delete session'));
      setIsDeleting(false);
    }
  };

  const handleSignOut = async () => {
    await signOut({ redirectUrl: '/' });
  };

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  if (!isLoaded || isLoading) {
    return (
      <div className="min-h-screen bg-[#f5f2ec] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-bright-green/20 border-t-bright-green animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f5f2ec]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#f5f2ec]/90 backdrop-blur-md border-b border-black/5">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-3">
            <Image
              src="/logo-light.png"
              alt="Etheria"
              width={100}
              height={30}
              style={{
                height: '26px',
                width: 'auto',
                filter: 'invert(1) sepia(1) saturate(0) brightness(0.2)',
              }}
              priority
            />
          </Link>

          <nav className="flex items-center gap-6">
            <Link
              href="/dashboard"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Chat
            </Link>
            <Link
              href="/dashboard/upload"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Documents
            </Link>
            <Link
              href="/dashboard/history"
              className="font-sans text-[13px] text-dark-text font-medium"
            >
              History
            </Link>
            <Link
              href="/dashboard/account"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Account
            </Link>
            <button
              onClick={handleSignOut}
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Sign Out
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Back link */}
        <Link
          href="/dashboard/history"
          className="inline-flex items-center gap-2 font-sans text-[13px] text-light-text hover:text-dark-text transition-colors mb-6"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to History
        </Link>

        {/* Error state */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <svg
              className="w-5 h-5 text-red-500 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="font-sans text-[13px] text-red-700">{error}</p>
          </div>
        )}

        {/* Session not found */}
        {!session && !isLoading && !error && (
          <div className="rounded-2xl border border-black/10 bg-white/60 p-12 text-center">
            <p className="font-sans text-[16px] text-dark-text font-medium">Session not found</p>
            <p className="font-sans text-[13px] text-light-text mt-2">
              This conversation may have been deleted.
            </p>
            <Link
              href="/dashboard/history"
              className="inline-flex items-center gap-2 mt-6 px-5 py-2.5 rounded-full bg-[#162a1c] font-sans text-[13px] font-medium text-cream transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
            >
              View All History
            </Link>
          </div>
        )}

        {/* Session content */}
        {session && (
          <>
            {/* Session header */}
            <div className="rounded-2xl border border-black/10 bg-white p-6 mb-6">
              <div className="flex items-start justify-between">
                <div>
                  {session.name && (
                    <p className="font-sans text-[16px] font-medium text-dark-text mb-1">
                      {session.name}
                    </p>
                  )}
                  <p className="font-sans text-[12px] text-light-text mb-1">
                    {formatDate(session.startedAt)}
                  </p>
                  <p className="font-sans text-[14px] text-dark-text">
                    {session.messages.length} message{session.messages.length !== 1 ? 's' : ''}
                  </p>
                </div>

                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-light-text hover:text-red-500 hover:bg-red-50 transition-all disabled:opacity-50"
                >
                  {isDeleting ? (
                    <span className="w-4 h-4 rounded-full border-2 border-light-text/20 border-t-light-text animate-spin" />
                  ) : (
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="1.5"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                      />
                    </svg>
                  )}
                  <span className="font-sans text-[13px]">Delete</span>
                </button>
              </div>

              {/* Triage level */}
              {session.triageLevel && (
                <div className="mt-4">
                  <TriageBadge level={session.triageLevel} />
                </div>
              )}
            </div>

            {/* Messages */}
            <div className="space-y-4">
              {session.messages.map((msg, idx) => (
                <MessageBubble
                  key={msg.messageId ?? idx}
                  role={msg.role as 'user' | 'assistant'}
                  content={msg.content}
                  timestamp={msg.timestamp}
                />
              ))}
            </div>

            {/* Continue conversation CTA */}
            <div className="mt-8 rounded-2xl border border-black/10 bg-white p-6 text-center">
              <p className="font-sans text-[14px] text-dark-text mb-4">
                Want to continue this conversation?
              </p>
              <Link
                href={`/dashboard?session=${sessionId}`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#162a1c] font-sans text-[13px] font-medium text-cream transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
              >
                Continue Chat
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                  />
                </svg>
              </Link>
            </div>

            {/* Disclaimer */}
            <p className="mt-6 font-sans text-[11px] text-light-text text-center">
              This is a record of your past conversation. For current health concerns, please start
              a new assessment.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
