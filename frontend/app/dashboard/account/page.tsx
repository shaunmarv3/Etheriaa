'use client';

import { clearSession, useAuth, useClerk, useUser } from '../../../src/lib/auth';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { deleteAccount, errorMessage } from '../../../src/lib/api';
import { useStore } from '../../../src/lib/store';

const CONFIRM_WORD = 'DELETE';

export default function AccountPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const router = useRouter();
  const resetChat = useStore((s) => s.resetChat);

  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoaded && !isSignedIn && !deleting) router.push('/sign-in');
  }, [isLoaded, isSignedIn, deleting, router]);

  const handleSignOut = async () => {
    resetChat();
    await signOut({ redirectUrl: '/' });
  };

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    if (confirmText !== CONFIRM_WORD) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount();
      resetChat();
      clearSession();
      router.push('/?account=deleted');
    } catch (err) {
      setError(errorMessage(err, 'Could not delete your account.'));
      setDeleting(false);
    }
  };

  if (!isLoaded || !user) {
    return (
      <div className="min-h-screen bg-[#f5f2ec] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-bright-green/20 border-t-bright-green animate-spin" />
      </div>
    );
  }

  const email = user.emailAddresses[0]?.emailAddress ?? '';

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
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              History
            </Link>
            <Link
              href="/dashboard/account"
              className="font-sans text-[13px] text-dark-text font-medium"
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

      <main className="max-w-3xl mx-auto px-6 py-12">
        <div className="mb-10">
          <p className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-2">
            Account
          </p>
          <h1 className="font-flare text-[clamp(32px,5vw,48px)] font-normal text-dark-text leading-[0.95] tracking-[-0.02em]">
            Your
            <br />
            <span className="italic">account</span>
          </h1>
        </div>

        {/* Details */}
        <section className="rounded-2xl border border-black/10 bg-white p-6 mb-6">
          <dl className="grid grid-cols-[120px_1fr] gap-y-3 font-sans text-[14px]">
            <dt className="text-light-text">Email</dt>
            <dd className="text-dark-text">{email}</dd>
            {user.firstName && (
              <>
                <dt className="text-light-text">Name</dt>
                <dd className="text-dark-text">{user.firstName}</dd>
              </>
            )}
          </dl>
          <button
            onClick={handleSignOut}
            className="mt-6 px-5 h-10 rounded-full border border-black/10 font-sans text-[13px] font-medium text-dark-text hover:bg-black/5 transition-colors"
          >
            Sign out
          </button>
        </section>

        {/* Delete account */}
        <section className="rounded-2xl border border-red-200 bg-red-50/60 p-6">
          <h2 className="font-sans text-[15px] font-semibold text-red-800">Delete account</h2>
          <p className="mt-2 font-sans text-[13px] leading-[1.6] text-red-800/80">
            This permanently deletes your account, every conversation, every uploaded document and
            everything extracted from them. It cannot be undone. The security audit log keeps a
            pseudonymous record (no health content) for one year.
          </p>

          {error && <p className="mt-3 font-sans text-[13px] text-red-700">{error}</p>}

          <form onSubmit={handleDelete} className="mt-4 flex flex-wrap items-center gap-3">
            <label htmlFor="confirm-delete" className="font-sans text-[13px] text-red-800">
              Type <span className="font-semibold">{CONFIRM_WORD}</span> to confirm
            </label>
            <input
              id="confirm-delete"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              disabled={deleting}
              autoComplete="off"
              className="h-10 w-40 rounded-lg border border-red-200 bg-white px-3 font-sans text-[14px] text-dark-text outline-none focus:border-red-400"
            />
            <button
              type="submit"
              disabled={confirmText !== CONFIRM_WORD || deleting}
              className="px-5 h-10 rounded-full bg-red-600 font-sans text-[13px] font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {deleting ? 'Deleting…' : 'Delete my account'}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
