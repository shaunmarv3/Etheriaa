'use client';

import { useAuth, useClerk } from '../../../src/lib/auth';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  fetchHistory,
  deleteSession,
  renameSession,
  errorMessage,
  type SessionSummary,
} from '../../../src/lib/api';
import type { TriageLevel } from '../../../src/lib/types';

// Inline SessionCard component
function SessionCard({
  sessionId,
  name,
  triageLevel,
  startedAt,
  messageCount,
  preview,
  onDelete,
  onRename,
  isDeleting,
}: {
  sessionId: string;
  name: string | null;
  triageLevel: TriageLevel | null;
  startedAt: string;
  messageCount: number;
  preview: string;
  onDelete?: (sessionId: string) => void;
  onRename?: (sessionId: string, name: string) => Promise<void>;
  isDeleting?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  // The backend names a new conversation after the start of its first message; show a
  // name only when it adds something to the preview.
  const title = name && !preview.startsWith(name) ? name : null;
  const [draft, setDraft] = useState(name ?? '');

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return 'Today, ' + date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    } else if (diffDays === 1) {
      return (
        'Yesterday, ' + date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
      );
    } else if (diffDays < 7) {
      return date.toLocaleDateString('en-US', {
        weekday: 'long',
        hour: 'numeric',
        minute: '2-digit',
      });
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getTriageBadge = () => {
    if (!triageLevel) return null;

    const config = {
      RED: {
        bg: 'bg-red-50',
        border: 'border-red-200',
        dot: 'bg-red-500',
        text: 'text-red-700',
        label: 'Urgent',
      },
      YELLOW: {
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        dot: 'bg-amber-500',
        text: 'text-amber-700',
        label: 'Moderate',
      },
      GREEN: {
        bg: 'bg-green-50',
        border: 'border-green-200',
        dot: 'bg-green-500',
        text: 'text-green-700',
        label: 'Low',
      },
    };

    const c = config[triageLevel];

    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${c.bg} border ${c.border}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        <span className={`font-sans text-[10px] font-medium ${c.text} uppercase tracking-wide`}>
          {c.label}
        </span>
      </span>
    );
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(sessionId);
    }
  };

  const handleRenameClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDraft(name ?? preview.slice(0, 60));
    setEditing(true);
  };

  const submitRename = async (e: React.FormEvent) => {
    e.preventDefault();
    const next = draft.trim();
    if (next && next !== name && onRename) await onRename(sessionId, next);
    setEditing(false);
  };

  if (editing) {
    return (
      <form
        onSubmit={submitRename}
        className="rounded-xl border border-bright-green/40 bg-white p-5 flex items-center gap-3"
      >
        <input
          autoFocus
          value={draft}
          maxLength={100}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
          aria-label="Conversation name"
          className="flex-1 h-10 rounded-lg border border-black/10 px-3 font-sans text-[14px] text-dark-text outline-none focus:border-bright-green"
        />
        <button
          type="submit"
          className="px-4 h-10 rounded-full bg-[#162a1c] font-sans text-[13px] font-medium text-cream"
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="px-3 h-10 font-sans text-[13px] text-light-text hover:text-dark-text"
        >
          Cancel
        </button>
      </form>
    );
  }

  return (
    <Link href={`/dashboard/history/${sessionId}`}>
      <div className="group relative rounded-xl border border-black/10 bg-white p-5 transition-all duration-200 hover:border-black/20 hover:shadow-md hover:-translate-y-0.5 cursor-pointer">
        {/* Header Row */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3">
            {getTriageBadge()}
            <span className="font-sans text-[12px] text-light-text">{formatDate(startedAt)}</span>
          </div>

          <div className="flex items-center gap-1">
            {/* Rename button */}
            {onRename && (
              <button
                onClick={handleRenameClick}
                className="p-1.5 rounded-lg text-light-text/40 hover:text-dark-text hover:bg-black/5 transition-all opacity-0 group-hover:opacity-100"
                title="Rename conversation"
              >
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
                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"
                  />
                </svg>
              </button>
            )}
            {/* Delete button */}
            {onDelete && (
              <button
                onClick={handleDeleteClick}
                disabled={isDeleting}
                className="p-1.5 rounded-lg text-light-text/40 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100 disabled:opacity-50"
                title="Delete session"
              >
                {isDeleting ? (
                  <span className="w-4 h-4 flex items-center justify-center">
                    <span className="w-3 h-3 rounded-full border-2 border-light-text/20 border-t-light-text animate-spin" />
                  </span>
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
              </button>
            )}
          </div>
        </div>

        {/* Name + preview */}
        {title && (
          <p className="font-sans text-[15px] font-medium text-dark-text leading-[1.4] mb-1">
            {title}
          </p>
        )}
        <p
          className={`font-sans leading-[1.5] line-clamp-2 ${
            title ? 'text-[13px] text-light-text' : 'text-[14px] text-dark-text'
          }`}
        >
          {preview || 'No messages in this session'}
        </p>

        {/* Footer */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-black/5">
          <svg
            className="w-4 h-4 text-light-text/60"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
            />
          </svg>
          <span className="font-sans text-[12px] text-light-text">
            {messageCount} message{messageCount !== 1 ? 's' : ''}
          </span>

          {/* Arrow indicator */}
          <svg
            className="w-4 h-4 text-light-text/40 ml-auto transition-transform group-hover:translate-x-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </div>
      </div>
    </Link>
  );
}

export default function HistoryPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const { signOut } = useClerk();
  const router = useRouter();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalSessions, setTotalSessions] = useState(0);
  const pageSize = 10;

  // Redirect if not signed in
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push('/sign-in');
    }
  }, [isLoaded, isSignedIn, router]);

  // Load sessions (state is set in the promise callbacks, not the effect body)
  useEffect(() => {
    if (!isSignedIn) return;
    let cancelled = false;
    fetchHistory(page, pageSize)
      .then((result) => {
        if (cancelled) return;
        setSessions(result.sessions);
        setTotalSessions(result.total);
        setError(null);
      })
      .catch((err) => !cancelled && setError(errorMessage(err, 'Failed to load history')))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, page]);

  const goToPage = (next: number) => {
    setIsLoading(true);
    setPage(next);
  };

  const handleDelete = async (sessionId: string) => {
    setIsDeleting(sessionId);
    setError(null);

    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.sessionId !== sessionId));
      setTotalSessions((prev) => prev - 1);
    } catch (err) {
      setError(errorMessage(err, 'Failed to delete session'));
    } finally {
      setIsDeleting(null);
    }
  };

  const handleRename = async (sessionId: string, name: string) => {
    setError(null);
    try {
      await renameSession(sessionId, name);
      setSessions((prev) => prev.map((s) => (s.sessionId === sessionId ? { ...s, name } : s)));
    } catch (err) {
      setError(errorMessage(err, 'Failed to rename conversation'));
    }
  };

  const handleSignOut = async () => {
    await signOut({ redirectUrl: '/' });
  };

  const totalPages = Math.ceil(totalSessions / pageSize);

  if (!isLoaded) {
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
      <main className="max-w-3xl mx-auto px-6 py-12">
        {/* Page Header */}
        <div className="mb-10">
          <p className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-2">
            History
          </p>
          <h1 className="font-flare text-[clamp(32px,5vw,48px)] font-normal text-dark-text leading-[0.95] tracking-[-0.02em]">
            Your past
            <br />
            <span className="italic">conversations</span>
          </h1>
          <p className="mt-4 font-sans text-[14px] text-light-text leading-[1.6] max-w-lg">
            Review your previous health assessments. Rename or delete them here.
          </p>
        </div>

        {/* Error message */}
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

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-bright-green/20 border-t-bright-green animate-spin" />
          </div>
        )}

        {/* Empty state */}
        {!isLoading && sessions.length === 0 && (
          <div className="rounded-2xl border border-black/10 bg-white/60 p-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-black/5 flex items-center justify-center mx-auto mb-5">
              <svg
                className="w-8 h-8 text-light-text"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                />
              </svg>
            </div>
            <p className="font-sans text-[16px] text-dark-text font-medium">No conversations yet</p>
            <p className="font-sans text-[13px] text-light-text mt-2">
              Start a new health assessment to begin tracking your conversations.
            </p>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 mt-6 px-5 py-2.5 rounded-full bg-[#162a1c] font-sans text-[13px] font-medium text-cream transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
            >
              Start New Chat
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
        )}

        {/* Sessions List */}
        {!isLoading && sessions.length > 0 && (
          <>
            <div className="space-y-3">
              {sessions.map((session) => (
                <SessionCard
                  key={session.sessionId}
                  sessionId={session.sessionId}
                  name={session.name}
                  triageLevel={session.triageLevel}
                  startedAt={session.startedAt}
                  messageCount={session.messageCount}
                  preview={session.preview}
                  onDelete={handleDelete}
                  onRename={handleRename}
                  isDeleting={isDeleting === session.sessionId}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => goToPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="p-2 rounded-lg border border-black/10 bg-white hover:bg-black/5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <svg
                    className="w-4 h-4 text-dark-text"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 19.5L8.25 12l7.5-7.5"
                    />
                  </svg>
                </button>

                <span className="font-sans text-[13px] text-light-text px-3">
                  Page {page} of {totalPages}
                </span>

                <button
                  onClick={() => goToPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="p-2 rounded-lg border border-black/10 bg-white hover:bg-black/5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <svg
                    className="w-4 h-4 text-dark-text"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M8.25 4.5l7.5 7.5-7.5 7.5"
                    />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
